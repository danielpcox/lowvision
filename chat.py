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


class ChatLogger:
    def __init__(self, config: argparse.Namespace, old_term_settings: list):
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
                    print("GOT HERE")
                    print("Line buffer:", self.line_buffer)
                    print("Message:", message)
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
        Your responses will be ready aloud by a screen reader line-by-line, so keep it very brief, format accordingly,
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
        try:
            while True:
                prompt = input("?> ")
                if prompt.strip() == "":
                    continue
                if prompt.strip() == "exit":
                    # Put the terminal back in cbreak mode after the chat
                    # tty.setcbreak(sys.stdin.fileno())
                    raise ChatInterruption
                self.conversation.append({"role": "user", "content": prompt})
                async for line in fetch_chat_completion(self.conversation):
                    print(line)
                    self.conversation.append({"role": "assistant", "content": line})
                    subprocess.run("say -v Daniel --rate 220 -f -", shell=True, text=True, input=line)
        except KeyboardInterrupt:
            pass  # Return control to the shell wrapper


async def fetch_chat_completion(prompt, model="gpt-4"):
    response = openai.ChatCompletion.create(
        model=model,
        messages=prompt,
        stream=True,
    )
    line = []
    for chunk in response:
        delta = chunk['choices'][0]['delta']
        if 'content' in delta:
            content = delta['content']
            # print("CONTENT:", content)
            if '\n' in content:
                segments = content.split('\n', 1)
                ending = "\n".join(segments[:-1])
                remainder = segments[-1]
                line.append(f'{ending}\n')
                yield "".join(line)
                line = [remainder]
            else:
                line.append(content)
        await asyncio.sleep(0)

    if line:
        yield "".join(line)


async def split_markdown_chunks(prompt, max_chars=1900):
    # lines = markdown_text.splitlines(True)  # Keep line breaks in the list elements
    current_chunk = ""
    in_code_block = False
    language = ""

    async for line in fetch_chat_completion(prompt):
        # print("LINE:", line)
        if line.startswith(which := "```") or line.startswith(which := "\n```"):
            language = line[len(which):].strip()

            # Code blocks always get their own chunk
            if not current_chunk:
                current_chunk += line
            elif not in_code_block:
                yield current_chunk
                current_chunk = line
            else:
                current_chunk += line
                yield current_chunk
                current_chunk = ""
            in_code_block = not in_code_block

        # continue to extend the current chunk
        elif len(current_chunk) + len(line) <= max_chars:
            current_chunk += line
            if not in_code_block:  # just print the line
                yield current_chunk
                current_chunk = ""

        # write out the current chunk and start a new one
        else:

            # code blocks need to be split into two functional code blocks
            if in_code_block:
                current_chunk += "```\n"
                yield current_chunk
                current_chunk = f"```{language}\n"
                current_chunk += line
            else:
                yield current_chunk
                current_chunk = line

    if current_chunk:
        yield current_chunk


class ChatInterruption(Exception):
    pass