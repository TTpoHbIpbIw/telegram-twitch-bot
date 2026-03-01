import os
import re
import socket
import time
import threading
from datetime import datetime
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder

# =============================
# НАСТРОЙКИ
# =============================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TWITCH_NICK = os.environ["TWITCH_NICK"]          # TTpoHbIpbIw_bot
TWITCH_OAUTH = os.environ["TWITCH_OAUTH"]

CHANNEL_NAME = "TTpoHbIpbIw"                     # твой канал
TWITCH_CHANNEL = f"#{CHANNEL_NAME}"
CHANNEL_OWNER = "ttpohbipbiw"

TRIGGER = "#анонс"
COOLDOWN_SECONDS = 30
ANNOUNCE_FILE = "announce.txt"

last_announce = None
last_announce_date = None
user_cooldowns = {}

twitch_started = False   # защита от двойного запуска

# =============================
# FLASK
# =============================
app = Flask(__name__)

# =============================
# ФАЙЛ
# =============================
def load_announce():
    global last_announce, last_announce_date
    if os.path.exists(ANNOUNCE_FILE):
        with open(ANNOUNCE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if len(lines) >= 2:
                last_announce = lines[0].strip()
                last_announce_date = datetime.strptime(
                    lines[1].strip(), "%Y-%m-%d"
                ).date()

def save_announce(message):
    with open(ANNOUNCE_FILE, "w", encoding="utf-8") as f:
        f.write(message + "\n")
        f.write(str(datetime.now().date()))

load_announce()

# =============================
# TWITCH LISTENER
# =============================
def twitch_listener():
    sock = socket.socket()
    sock.connect(("irc.chat.twitch.tv", 6667))
    sock.send(f"PASS {TWITCH_OAUTH}\r\n".encode())
    sock.send(f"NICK {TWITCH_NICK}\r\n".encode())
    sock.send(f"JOIN {TWITCH_CHANNEL}\r\n".encode())

    while True:
        resp = sock.recv(2048).decode()

        if resp.startswith("PING"):
            sock.send("PONG :tmi.twitch.tv\r\n".encode())
            continue

        if "PRIVMSG" in resp:
            prefix = resp.split("PRIVMSG")[0]
            username = prefix.split("!")[0].replace(":", "").lower()
            message = resp.split("PRIVMSG")[1].split(":",1)[1].strip()

            # анти-луп
            if username == TWITCH_NICK.lower():
                continue

            if message.lower() == "!анонс":
                today = datetime.now().date()

                if username == CHANNEL_OWNER:
                    reply = last_announce if last_announce and last_announce_date == today else "Сегодня не было анонса"
                else:
                    now = time.time()
                    last_used = user_cooldowns.get(username, 0)

                    if now - last_used < COOLDOWN_SECONDS:
                        reply = "Подожди немного перед повторным вызовом команды"
                    else:
                        user_cooldowns[username] = now
                        reply = last_announce if last_announce and last_announce_date == today else "Сегодня не было анонса"

                sock.send(f"PRIVMSG {TWITCH_CHANNEL} :{reply}\r\n".encode())

# =============================
# TELEGRAM WEBHOOK
# =============================
telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

@app.route("/", methods=["POST"])
async def telegram_webhook():
    global last_announce, last_announce_date

    update = Update.de_json(request.get_json(), telegram_app.bot)

    if update.channel_post:
        text = update.channel_post.text or update.channel_post.caption
        if text and TRIGGER in text.lower():
            text_no_tags = re.sub(r"#\w+", "", text)
            clean_text = " ".join(text_no_tags.split())
            final_message = f"📢 {clean_text} 🔴 twitch.tv/{CHANNEL_NAME}"

            last_announce = final_message
            last_announce_date = datetime.now().date()
            save_announce(final_message)

    return "ok"

# =============================
# MAIN
# =============================
def main():
    global twitch_started

    # ставим webhook
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    telegram_app.bot.set_webhook(webhook_url)

    # запускаем Twitch только один раз
    if not twitch_started:
        twitch_started = True
        threading.Thread(target=twitch_listener, daemon=True).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
