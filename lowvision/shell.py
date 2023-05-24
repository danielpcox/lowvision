import argparse
import asyncio
import errno
import fcntl
import os
import pty
import signal
import struct
import sys
import termios
from select import select

import lowvision.chat as chat


def get_terminal_size():
    size = struct.unpack('hh', fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, '1234'))
    return size


def set_terminal_size(fd, size):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('hh', *size))


async def main(config):
    pid, master_fd = pty.fork()

    if pid == 0:
        # Child process
        os.execv(config.shell, [config.shell])
    else:
        print(f"\nStarting chat-aware shell wrapper around {config.shell}. "
              "Run `chat` to enter chat mode. Exit with `exit`. "
              "Ctrl-C interrupts text-to-speech. "
              "Exit and re-run with `-h` to see options.")
        print("Option values: ", config.__dict__, "\n")
        # Parent process
        shell_pid = pid

        def handle_signals(signal_number, frame):
            os.kill(shell_pid, signal_number)

        def handle_window_resize(signum, frame):
            size = get_terminal_size()
            set_terminal_size(master_fd, size)

        signal.signal(signal.SIGWINCH, handle_window_resize)
        signal.signal(signal.SIGINT, handle_signals)
        signal.signal(signal.SIGTSTP, handle_signals)

        set_terminal_size(master_fd, get_terminal_size())

        old_term_settings = termios.tcgetattr(sys.stdin.fileno())

        logger = chat.ChatLogger(config, old_term_settings)
        try:
            new_term_settings = termios.tcgetattr(sys.stdin.fileno())
            new_term_settings[3] = new_term_settings[3] & ~termios.ICANON & ~termios.ECHO
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, new_term_settings)

            while True:
                try:
                    r_fd, _, _ = select([sys.stdin, master_fd], [], [])

                    if sys.stdin in r_fd:
                        input_data = os.read(sys.stdin.fileno(), 1024)
                        if not input_data:
                            break
                        os.write(master_fd, input_data)

                    if master_fd in r_fd:
                        output_data = os.read(master_fd, 1024)
                        if not output_data:
                            break

                        try:
                            await logger.log(output_data)
                            os.write(sys.stdout.fileno(), output_data)
                        except chat.ChatInterruption:
                            continue
                        finally:
                            termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, new_term_settings)
                            signal.signal(signal.SIGINT, handle_signals)

                except OSError as e:
                    if e.errno == errno.EIO:
                        break

        finally:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, old_term_settings)
            os.close(master_fd)


if __name__ == "__main__":
    # argparse to get the shell and the size of the scrollback buffer (defaults to 1000 lines)
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/bash')
    parser.add_argument('--scrollback', default=2000, type=int)
    parser.add_argument('--model', default='gpt-3.5-turbo')
    parser.add_argument('--tts', default='espeak -v en-us -s 220')
    parser.add_argument('--no-tts', action='store_true')

    args = parser.parse_args()
    asyncio.run(main(args))
