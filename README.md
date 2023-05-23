# Tools for low-vision coders

## Shell Chat

A wrapper for your shell that lets you talk to ChatGPT about the recent interactions.

1. Wraps bash or another shell you pass in, so that it behaves exactly like what you'd expect.
2. Except that when you run the "chat" command, it switches into a separate mode where you're talking to ChatGPT about the past 1k (configurable) lines of interaction.
3. You have a back and forth conversation, and all of ChatGPT's responses are read aloud.
4. You can Control-C to interrupt and go back to the chat prompt.
5. You type "exit" to go back to your shell.
6. You can also type "pdb" at the chat prompt to drop into the debugger.

`pip install lowvision`

`python -m lowvision.shell -h`