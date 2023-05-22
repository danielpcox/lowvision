import argparse
import asyncio
import os
import pty
import select
import signal
import sys
import termios
import tty

import chat


# Wraps bash to maintain a buffer of recent IO to discuss with ChatGPT
async def main(config: argparse.Namespace):
    pid, fd = pty.fork()

    def signal_handler(signum, frame):
        os.write(fd, b'\x03')

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTSTP, signal_handler)

    if pid == 0:  # child process
        os.execv(config.shell, [config.shell])
    else:  # parent process
        old_settings = termios.tcgetattr(sys.stdin)
        logger = chat.ChatLogger(config, old_settings)
        tty.setcbreak(sys.stdin.fileno())

        poller = select.poll()
        poller.register(sys.stdin, select.POLLIN)
        poller.register(fd, select.POLLIN | select.POLLHUP | select.POLLERR)

        try:
            while True:
                events = poller.poll()
                for event_fd, event in events:
                    if event_fd == sys.stdin.fileno() and event & select.POLLIN:
                        data = os.read(sys.stdin.fileno(), 1024)
                        os.write(fd, data)
                    elif event_fd == fd:
                        data = os.read(fd, 1024)
                        if data:
                            try:
                                await logger.log(data)
                                os.write(sys.stdout.fileno(), data)
                            except chat.ChatInterruption:
                                continue
                        else:
                            poller.unregister(fd)
                            break
                if not any(items[1] & (select.POLLIN | select.POLLHUP | select.POLLERR) for items in events):
                    break
        except OSError:
            pass
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            os.close(fd)


if __name__ == "__main__":
    # argparse to get the shell and the size of the scrollback buffer (defaults to 1000 lines)
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/bash')
    parser.add_argument('--scrollback', default=1000, type=int)
    parser.add_argument('--model', default='gpt-4')
    #parser.add_argument('--speak_cmd', default='say -v Daniel --rate 220 -f -')
    parser.add_argument('--speak_cmd', default='espeak -v en-us -s 220')
    args = parser.parse_args()
    asyncio.run(main(args))
