import argparse
import asyncio
import io
import pdb
import subprocess
import sys
import termios
import textwrap
import tty
from datetime import datetime, timezone

import openai
from aioconsole import ainput


class ChatLogger:
    def __init__(self, config: argparse.Namespace, old_term_settings: list):
        self.config = config
        self.old_settings = old_term_settings
        self.line_buffer = ''
        self.scrollback = ''
        self.max_chars = config.scrollback
        self.conversation = []

    async def log(self, message: bytes):
        message = message.decode('utf-8', errors='ignore').replace('\r', '')
        self.line_buffer += message
        if '\n' in self.line_buffer:
            lines = self.line_buffer.split('\n')
            self.line_buffer = lines.pop()
            for line in lines:
                if line.endswith("chat"):
                    await self.chat_mode()
                new_line = line + '\n'
                self.scrollback += new_line
                while len(self.scrollback) > self.max_chars:
                    pos = self.scrollback.find('\n') + 1
                    self.scrollback = self.scrollback[pos:]

    def reset_conversation(self):
        dt = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')
        system_prompt = textwrap.dedent(f"""
        You are a helpful command line troubleshooting assistant with knowledge of events up to 2021-09.
        Your responses will be read aloud by a screen reader line-by-line, so keep it very brief, format accordingly,
        and frequently break things up by new lines whenever possible.
        Right now it is {dt}, and the user's terminal scrollback buffer is:
        
        {self.scrollback}
        """)
        self.conversation = [
            {"role": "system", "content": system_prompt}
        ]

    async def chat_mode(self):
        # Put the terminal back in line-buffered mode for the chat
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        print()
        self.reset_conversation()
        while True:
            try:
                prompt = await ainput("?> ")
            except EOFError:
                break
            if prompt.strip() == "":
                continue
            if prompt.strip() == "exit":
                break
            if prompt.strip() == "pdb":
                pdb.set_trace()
                continue
            self.conversation.append({"role": "user", "content": prompt})
            q = asyncio.Queue()
            asyncio.create_task(self.speak(q))
            async for line in self.fetch_chat_completion(self.conversation):
                self.conversation.append({"role": "assistant", "content": line})
                # pdb.set_trace()
                # subprocess.run(self.config.tts, shell=True, text=True, input=line, check=True)
                await q.put(line)
            await q.put(None)  # terminate the speaking coroutine
            print()

        raise ChatInterruption

    async def speak(self, q: asyncio.Queue):
        while True:
            line = await q.get()
            if line is None:
                break
            proc = await asyncio.create_subprocess_shell(self.config.tts, stdin=asyncio.subprocess.PIPE)
            proc.stdin.write(line.encode())
            await proc.stdin.drain()
            proc.stdin.close()
            await proc.wait()
            q.task_done()

    # Asyncify the OpenAI API responses so we don't interrupt speech
    async def fetch_chat_completion(self, prompt):
        loop = asyncio.get_running_loop()
        generator = self._fetch_chat_completion(prompt)

        def next_from_generator():
            try:
                return next(generator)
            except StopIteration:
                return None

        while True:
            chunk = await asyncio.to_thread(next_from_generator)
            if chunk is None:
                break

            yield chunk

    def _fetch_chat_completion(self, prompt):
        response = openai.ChatCompletion.create(
            model=self.config.model,
            messages=prompt,
            stream=True,
        )
        line = []
        for chunk in response:
            delta = chunk['choices'][0]['delta']
            if 'content' in delta:
                content = delta['content']
                sys.stdout.write(content)
                sys.stdout.flush()
                if '\n' in content:
                    segments = content.split('\n', 1)
                    ending = "\n".join(segments[:-1])
                    remainder = segments[-1]
                    line.append(f'{ending}\n')
                    yield "".join(line)
                    line = [remainder]
                else:
                    line.append(content)

        if line:
            yield "".join(line)


class ChatInterruption(Exception):
    pass
