import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import socket
import os
import re

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TWITCH_NICK = os.environ["TWITCH_NICK"]
TWITCH_CHANNEL = f"#{TWITCH_NICK}"
TWITCH_OAUTH = os.environ["TWITCH_OAUTH"]

TRIGGER = "#анонс"

def send_to_twitch(message):
    sock = socket.socket()
    sock.connect(("irc.chat.twitch.tv", 6667))
    sock.send(f"PASS {TWITCH_OAUTH}\r\n".encode("utf-8"))
    sock.send(f"NICK {TWITCH_NICK}\r\n".encode("utf-8"))
    sock.send(f"JOIN {TWITCH_CHANNEL}\r\n".encode("utf-8"))
    sock.send(f"PRIVMSG {TWITCH_CHANNEL} :{message[:450]}\r\n".encode("utf-8"))
    sock.close()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post:

        text = None

        if update.channel_post.text:
            text = update.channel_post.text
        elif update.channel_post.caption:
            text = update.channel_post.caption

        if text and TRIGGER in text.lower():

            # Удаляем ВСЕ хэштеги
            text_no_tags = re.sub(r"#\w+", "", text)

            # Убираем лишние переносы строк
            clean_text = " ".join(text_no_tags.split())

            final_message = f"📢 {clean_text} 🔴 twitch.tv/{TWITCH_NICK}"

            send_to_twitch(final_message)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, handle_message))
app.run_polling()
