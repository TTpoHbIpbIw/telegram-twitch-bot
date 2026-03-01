import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import socket
import os
import re
from flask import Flask
from threading import Thread
from datetime import datetime
import time

# =============================
# WEB SERVER (для Render Free)
# =============================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

Thread(target=run_web).start()

# =============================
# НАСТРОЙКИ
# =============================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TWITCH_NICK = os.environ["TWITCH_NICK"]  # TTpoHbIpbIw_bot
TWITCH_OAUTH = os.environ["TWITCH_OAUTH"]

CHANNEL_NAME = "TTpoHbIpbIw"  # твой основной канал
TWITCH_CHANNEL = f"#{CHANNEL_NAME}"

CHANNEL_OWNER = "ttpohbipbiw"  # твой основной ник маленькими буквами
TRIGGER = "#анонс"
COOLDOWN_SECONDS = 30
ANNOUNCE_FILE = "announce.txt"

last_announce = None
last_announce_date = None
last_command_time = 0

# =============================
# ЗАГРУЗКА ИЗ ФАЙЛА
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

# =============================
# СОХРАНЕНИЕ В ФАЙЛ
# =============================
def save_announce(message):
    with open(ANNOUNCE_FILE, "w", encoding="utf-8") as f:
        f.write(message + "\n")
        f.write(str(datetime.now().date()))

load_announce()

# =============================
# ОТПРАВКА СООБЩЕНИЯ
# =============================
def send_message(sock, message):
    sock.send(
        f"PRIVMSG {TWITCH_CHANNEL} :{message[:450]}\r\n".encode("utf-8")
    )

# =============================
# TELEGRAM
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
# TWITCH LISTENER
# =============================
def listen_to_twitch():
    global last_command_time

    sock = socket.socket()
    sock.connect(("irc.chat.twitch.tv", 6667))
    sock.send(f"PASS {TWITCH_OAUTH}\r\n".encode("utf-8"))
    sock.send(f"NICK {TWITCH_NICK}\r\n".encode("utf-8"))
    sock.send(f"JOIN {TWITCH_CHANNEL}\r\n".encode("utf-8"))

    while True:
        resp = sock.recv(2048).decode("utf-8")

        if resp.startswith("PING"):
            sock.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
            continue

        if "PRIVMSG" in resp:
            if resp.count("PRIVMSG") > 1:
    continue
            prefix = resp.split("PRIVMSG")[0]
            username = prefix.split("!")[0].replace(":", "").lower()
            message = resp.split("PRIVMSG")[1].split(":", 1)[1].strip()

            # === АНТИ-ЛУП ===
            if username == TWITCH_NICK.lower():
                continue

            if message.lower() == "!анонс":
                today = datetime.now().date()

                # === БЕЗ КУЛДАУНА ДЛЯ ТЕБЯ ===
                if username == CHANNEL_OWNER:
                    if last_announce and last_announce_date == today:
                        send_message(sock, last_announce)
                    else:
                        send_message(sock, "Сегодня не было анонса")
                    continue

                # === КУЛДАУН ДЛЯ ЗРИТЕЛЕЙ ===
                now = time.time()
                if now - last_command_time < COOLDOWN_SECONDS:
                    send_message(sock, "Подожди немного перед повторным вызовом команды")
                    continue

                last_command_time = now

                if last_announce and last_announce_date == today:
                    send_message(sock, last_announce)
                else:
                    send_message(sock, "Сегодня не было анонса")

if os.environ.get("RUN_MAIN") != "true":
    Thread(target=listen_to_twitch, daemon=True).start()

# =============================
# ЗАПУСК TELEGRAM
# =============================
telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
telegram_app.add_handler(MessageHandler(filters.ALL, handle_message))
telegram_app.run_polling()
