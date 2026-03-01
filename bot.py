import os
import re
import socket
import time
import threading
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =============================
# НАСТРОЙКИ
# =============================
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

# =============================
# FLASK (только чтобы Render не засыпал)
# =============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

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
# TELEGRAM (POLLING)
# =============================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_announce, last_announce_date

    if update.channel_post:
        text = update.channel_post.text or update.channel_post.caption
        if text and TRIGGER in text.lower():
            text_no_tags = re.sub(r"#\w+", "", text)
            clean_text = " ".join(text_no_tags.split())
            final_message = f"📢 {clean_text} 🔴 twitch.tv/{CHANNEL_NAME}"

            last_announce = final_message
            last_announce_date = datetime.now().date()
            save_announce(final_message)

# =============================
# TWITCH
# =============================
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

            message_id = None
            if "id=" in resp:
                for tag in resp.split(";"):
                    if tag.startswith("id="):
                        message_id = tag.split("=")[1]
                        break

            if message_id and message_id in processed_ids:
                continue

            if message_id:
                processed_ids.add(message_id)
                if len(processed_ids) > 100:
                    processed_ids.clear()

            prefix = resp.split("PRIVMSG")[0]
            username = prefix.split("!")[0].split("@")[-1].lower()
            message = resp.split("PRIVMSG")[1].split(":",1)[1].strip()

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
# MAIN
# =============================
def main():
    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=twitch_listener, daemon=True).start()

    telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    telegram_app.add_handler(MessageHandler(filters.ALL, handle_message))

    telegram_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
