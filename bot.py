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

HASHTAG = "#анонс"

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

        # Если обычный текст
        if update.channel_post.text:
            text = update.channel_post.text

        # Если фото/видео с подписью
        elif update.channel_post.caption:
            text = update.channel_post.caption

        if text and HASHTAG in text.lower():
            clean_text = re.sub(HASHTAG, "", text, flags=re.IGNORECASE).strip()
            clean_text = clean_text.replace("\n", " ")
            final_message = f"📢 {clean_text} 🔴 twitch.tv/{TWITCH_NICK}"
            send_to_twitch(final_message)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, handle_message))
app.run_polling()
