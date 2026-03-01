import os
import re
import socket
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder

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
GLOBAL_COOLDOWN = 3  # защита от массового спама
ANNOUNCE_FILE = "announce.txt"

last_announce = None
last_announce_date = None
last_announce_time = 0

user_cooldowns = {}
processed_ids = set()

last_global_command_time = 0
last_sent_message = None

sock = None
twitch_started = False

# =============================
# FLASK
# =============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

# =============================
# СОХРАНЕНИЕ АНОНСА
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
# TELEGRAM WEBHOOK
# =============================
telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    global last_announce, last_announce_date, last_announce_time
    global sock, last_sent_message

    data = request.get_json(force=True, silent=True)
    update = Update.de_json(data, telegram_app.bot)

    text = None

    if update.channel_post:
        text = update.channel_post.text or update.channel_post.caption
    elif update.message:
        text = update.message.text or update.message.caption

    if text and TRIGGER in text.lower():

        text_no_tags = re.sub(r"#\w+", "", text)
        clean_text = " ".join(text_no_tags.split())
        final_message = f"📢 {clean_text} 🔴 twitch.tv/{CHANNEL_NAME}"

        # 🔒 Защита от двойного автопоста
        if final_message == last_announce and time.time() - last_announce_time < 10:
            return jsonify({"status": "duplicate blocked"})

        last_announce = final_message
        last_announce_date = datetime.now().date()
        last_announce_time = time.time()

        save_announce(final_message)

        # Авто-пост в Twitch
        if sock and final_message != last_sent_message:
            sock.send(f"PRIVMSG {TWITCH_CHANNEL} :{final_message}\r\n".encode())
            last_sent_message = final_message

    return jsonify({"status": "ok"})

# =============================
# TWITCH IRC
# =============================
def twitch_listener():
    global sock, twitch_started
    global last_global_command_time, last_sent_message

    if twitch_started:
        return

    twitch_started = True

    sock = socket.socket()
    sock.connect(("irc.chat.twitch.tv", 6667))
    sock.send(f"PASS {TWITCH_OAUTH}\r\n".encode())
    sock.send(f"NICK {TWITCH_NICK}\r\n".encode())
    sock.send("CAP REQ :twitch.tv/tags\r\n".encode())
    sock.send(f"JOIN {TWITCH_CHANNEL}\r\n".encode())

    print("TWITCH CONNECTED", flush=True)

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

            # 🔒 Анти-дубликат по ID
            if message_id and message_id in processed_ids:
                continue

            if message_id:
                processed_ids.add(message_id)
                if len(processed_ids) > 200:
                    processed_ids.clear()

            prefix = resp.split("PRIVMSG")[0]
            username = prefix.split("!")[0].split("@")[-1].lower()
            message = resp.split("PRIVMSG")[1].split(":",1)[1].strip()

            if username == TWITCH_NICK.lower():
                continue

            if message.lower() == "!анонс":

                now = time.time()

                # 🌍 Глобальный анти-спам
                if now - last_global_command_time < GLOBAL_COOLDOWN:
                    continue

                last_global_command_time = now

                # 👑 Без кулдауна для владельца
                if username != CHANNEL_OWNER:
                    last_used = user_cooldowns.get(username, 0)

                    if now - last_used < COOLDOWN_SECONDS:
                        continue

                    user_cooldowns[username] = now

                today = datetime.now().date()

                if last_announce and last_announce_date == today:
                    reply = last_announce
                else:
                    reply = "Сегодня не было анонса"

                # 🔒 Защита от повторной отправки того же сообщения
                if reply != last_sent_message:
                    sock.send(f"PRIVMSG {TWITCH_CHANNEL} :{reply}\r\n".encode())
                    last_sent_message = reply

# =============================
# MAIN
# =============================
if __name__ == "__main__":
    threading.Thread(target=twitch_listener, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
