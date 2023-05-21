import os
import pty
import select
import signal
import sys
import termios
import tty


class ShellLogger:
    def __init__(self, log_file):
        self.log_file = log_file
        self.output_buffer = ''

    def log(self, message):
        message = message.decode('utf-8', errors='ignore').replace('\r', '')
        with open(self.log_file, 'a') as file:
            self.output_buffer += message
            if '\n' in self.output_buffer:
                lines = self.output_buffer.split('\n')
                self.output_buffer = lines.pop()
                for line in lines:
                    file.write(f'{line}\n')


def main():
    log_file = 'bash.log'
    logger = ShellLogger(log_file)
    pid, fd = pty.fork()

    def signal_handler(signum, frame):
        os.write(fd, b'\x03')

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTSTP, signal_handler)

    if pid == 0:  # child process
        os.execv('/bin/bash', ['/bin/bash'])
    else:  # parent process

        old_settings = termios.tcgetattr(sys.stdin)
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
                            os.write(sys.stdout.fileno(), data)
                            logger.log(data)
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
    main()
