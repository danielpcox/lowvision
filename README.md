# Tools for low-vision coders

## Shell Chat

A wrapper for your shell that lets you talk to ChatGPT about the recent interactions.

1. Wraps bash or another shell you pass in, so that it behaves exactly like what you'd expect.
2. Except that when you run the `chat` command, it switches into a separate mode where you're talking to ChatGPT about the past 3k (configurable) characters of interaction.
3. You have a back and forth conversation, and all of ChatGPT's responses are read aloud.
4. You can `Ctrl-C` to interrupt and go back to the chat prompt.
5. You type `exit` to go back to your shell.

### Installation

```bash
pip install lowvision
```

Then set [your OpenAI API key](https://platform.openai.com/account/api-keys)
```bash
export OPENAI_API_KEY='whatever'
```

### Usage

See the help with 

```bash
python -m lowvision.shell -h
```

Without arguments, it will
- launch Bash
- with a 3000 character scrollback buffer
- use `espeak` for text-to-speech
- and `gpt-3.5-turbo` as the ChatGPT model

Here's an example that changes those defaults:

```bash
python -m lowvision.shell --shell /bin/sh \
                          --scrollback 5000 \
                          --tts 'say -v Daniel --rate 220' \
                          --model gpt-4
                          
sh-3.2$ ping -c 3 google.com
PING google.com (142.251.163.100): 56 data bytes
64 bytes from 142.251.163.100: icmp_seq=0 ttl=106 time=18.316 ms
^C
--- google.com ping statistics ---
1 packets transmitted, 1 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 18.316/18.316/18.316/0.000 ms
sh-3.2$ chat     
?> what happened?
The user performed a ping test to google.com by sending 3 packets, and received a reply from one packet. The response shows the IP address of google.com and the round-trip time for the packet. The test was interrupted with ^C after receiving one response.
?> exit
sh-3.2$
```

