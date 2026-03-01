import os
import re
import socket
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TWITCH_NICK = os.environ["TWITCH_NICK"]
TWITCH_OAUTH = os.environ["TWITCH_OAUTH"]

CHANNEL_NAME = "TTpoHbIpbIw"
TWITCH_CHANNEL = f"#{CHANNEL_NAME}"
CHANNEL_OWNER = "ttpohbipbiw"

TRIGGER = "#анонс"
COOLDOWN_SECONDS = 30
ANNOUNCE_FILE = "announce.txt"

last_announce = None
last_announce_date = None
user_cooldowns = {}
processed_ids = set()

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    print("WEBHOOK HIT")

    data = request.get_json(force=True, silent=True)
    print("RAW DATA:", data)

    if not data:
        return jsonify({"status": "no data"})

    update = Update.de_json(data, telegram_app.bot)

    text = None

    if update.channel_post:
        text = update.channel_post.text or update.channel_post.caption
    elif update.message:
        text = update.message.text or update.message.caption

    print("TEXT:", text)

    if text and TRIGGER in text.lower():
        final_message = f"📢 {text} 🔴 twitch.tv/{CHANNEL_NAME}"
        global last_announce, last_announce_date
        last_announce = final_message
        last_announce_date = datetime.now().date()
        print("ANNOUNCE SAVED")

    return jsonify({"status": "ok"})

def twitch_listener():
    sock = socket.socket()
    sock.connect(("irc.chat.twitch.tv", 6667))
    sock.send(f"PASS {TWITCH_OAUTH}\r\n".encode())
    sock.send(f"NICK {TWITCH_NICK}\r\n".encode())
    sock.send("CAP REQ :twitch.tv/tags\r\n".encode())
    sock.send(f"JOIN {TWITCH_CHANNEL}\r\n".encode())

    print("TWITCH CONNECTED")

    while True:
        resp = sock.recv(2048).decode(errors="ignore")

        if resp.startswith("PING"):
            sock.send("PONG :tmi.twitch.tv\r\n".encode())
            continue

        if "PRIVMSG" in resp:

            message = resp.split("PRIVMSG")[1].split(":",1)[1].strip()

            if message.lower() == "!анонс":
                today = datetime.now().date()
                if last_announce and last_announce_date == today:
                    reply = last_announce
                else:
                    reply = "Сегодня не было анонса"

                sock.send(f"PRIVMSG {TWITCH_CHANNEL} :{reply}\r\n".encode())

if __name__ == "__main__":
    threading.Thread(target=twitch_listener, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
