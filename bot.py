import socket
import os

TWITCH_NICK = os.environ["TWITCH_NICK"]
TWITCH_CHANNEL = f"#{TWITCH_NICK}"
TWITCH_OAUTH = os.environ["TWITCH_OAUTH"]

sock = socket.socket()
sock.connect(("irc.chat.twitch.tv", 6667))
sock.send(f"PASS {TWITCH_OAUTH}\r\n".encode("utf-8"))
sock.send(f"NICK {TWITCH_NICK}\r\n".encode("utf-8"))
sock.send(f"JOIN {TWITCH_CHANNEL}\r\n".encode("utf-8"))

response = sock.recv(2048).decode("utf-8")
print(response)

sock.close()
