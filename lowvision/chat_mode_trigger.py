from pathlib import Path

chat_mode_trigger = Path('/tmp/trigger_chat_mode')


def set_trigger():
    chat_mode_trigger.touch()
