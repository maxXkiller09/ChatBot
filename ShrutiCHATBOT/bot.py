"""Recovered Pyrogram bot package with a Render health endpoint."""
import asyncio
import logging
import os
import random
from collections import defaultdict, deque

import aiohttp
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.enums import ChatType
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("shruti")

required = {"API_ID": config.API_ID, "API_HASH": config.API_HASH,
            "BOT_TOKEN": config.BOT_TOKEN, "OWNER_ID": config.OWNER_ID}
missing = [key for key, value in required.items() if not value]
if missing:
    raise RuntimeError("Missing required environment variables: " + ", ".join(missing))

app = Client("shruti-chatbot", api_id=config.API_ID, api_hash=config.API_HASH,
             bot_token=config.BOT_TOKEN)
history = defaultdict(lambda: deque(maxlen=10))
enabled = defaultdict(lambda: True)

# Diagnostic handler: confirms whether Telegram updates reach this process.
@app.on_message(filters.all, group=-100)
async def log_incoming_update(_, message):
    sender_id = message.from_user.id if message.from_user else None
    log.info("Incoming Telegram update: chat_type=%s chat_id=%s sender_id=%s has_text=%s",
             message.chat.type, message.chat.id, sender_id, bool(message.text or message.caption))

@app.on_raw_update()
async def log_raw_update(_, update, users, chats):
    # Raw updates help distinguish Telegram delivery issues from message-handler issues.
    log.info("Raw Telegram update received: %s", type(update).__name__)

async def ask(base, key, model, messages):
    if not key:
        return None
    try:
        timeout = aiohttp.ClientTimeout(total=18)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(base.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + key},
                json={"model": model, "messages": messages, "max_tokens": 220, "temperature": 0.8}) as r:
                if r.status >= 400:
                    log.warning("AI provider returned HTTP %s", r.status)
                    return None
                data = await r.json()
                return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip() or None
    except Exception as exc:
        log.warning("AI provider error: %s", type(exc).__name__)
        return None

async def reply_ai(chat_id, text, name):
    messages = [{"role": "system", "content":
        "You are Shruti, a witty, friendly Gen-Z Telegram friend. Reply naturally in casual Hinglish, concise and context-aware. Do not claim to be human."}]
    messages.extend(list(history[chat_id])[-8:])
    messages.append({"role": "user", "content": f"{name}: {text[:1200]}"})
    answer = await ask(config.PRIMARY_AI_BASE_URL, config.PRIMARY_AI_API_KEY, config.PRIMARY_AI_MODEL, messages)
    if not answer:
        answer = await ask(config.BACKUP_AI_BASE_URL, config.BACKUP_AI_API_KEY, config.BACKUP_AI_MODEL, messages)
    return answer or "AYOOO 😭 AI API abhi set nahi hai ya respond nahi kar rahi."

@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text("AYOOO 👀 Shruti ChatBot online hai 😭\n/help se commands dekho.")

@app.on_message(filters.command("help"))
async def help_cmd(_, message):
    await message.reply_text("/start /help /ping /id /status /health /chatbot on|off /shayri")

@app.on_message(filters.command("ping"))
async def ping(_, message):
    await message.reply_text("Pong 🏓")

@app.on_message(filters.command("id"))
async def get_id(_, message):
    uid = message.from_user.id if message.from_user else "unknown"
    await message.reply_text(f"User ID: {uid}\nChat ID: {message.chat.id}")

@app.on_message(filters.command("status"))
async def status(_, message):
    ai = "configured" if config.PRIMARY_AI_API_KEY or config.BACKUP_AI_API_KEY else "missing API keys"
    await message.reply_text(f"Bot running. AI: {ai}")

@app.on_message(filters.command("health"))
async def health(_, message):
    if not message.from_user or message.from_user.id != config.OWNER_ID:
        return await message.reply_text("Owner-only command.")
    await message.reply_text("Health: Telegram handlers running. HTTP health endpoint is active.")

@app.on_message(filters.command("chatbot"))
async def chatbot(_, message):
    if not message.from_user or message.from_user.id != config.OWNER_ID:
        return await message.reply_text("Owner-only command.")
    args = (message.text or "").split(maxsplit=1)
    if message.chat.type == ChatType.PRIVATE or len(args) != 2 or args[1].lower() not in {"on", "off"}:
        return await message.reply_text("Group mein /chatbot on ya /chatbot off use karo.")
    enabled[message.chat.id] = args[1].lower() == "on"
    await message.reply_text("Chatbot " + args[1].lower() + " hai.")

@app.on_message(filters.new_chat_members)
async def welcome(_, message):
    templates = [
        "AYOOO 👀 welcome {first_name} 😭 GC mein chill karna, rules padh lena tho 🫡",
        "Welcome {first_name} ✨ GC ka vibe check pass karna padega 👀",
        "AYYY {first_name} joined the chaos 😭🔥 welcome welcome!",
    ]
    for member in message.new_chat_members:
        if not member.is_bot:
            await message.reply_text(random.choice(templates).format(first_name=member.first_name or "bestie"))

@app.on_message(filters.text & ~filters.command(["start", "help", "ping", "id", "status", "health", "chatbot"]))
async def chat(_, message):
    if not message.from_user or message.from_user.is_bot:
        return
    text = (message.text or "").strip()
    addressed = message.chat.type == ChatType.PRIVATE
    if message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        me = await app.get_me()
        addressed = bool(me.username and ("@" + me.username).lower() in text.lower())
        addressed = addressed or bool(message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == me.id)
        if not enabled[message.chat.id] or not addressed:
            return
        if me.username:
            text = text.replace("@" + me.username, "").strip()
    if not addressed:
        return
    history[message.chat.id].append({"role": "user", "content": f"{message.from_user.first_name}: {text[:1000]}"})
    answer = await reply_ai(message.chat.id, text, message.from_user.first_name or "friend")
    history[message.chat.id].append({"role": "assistant", "content": answer[:1000]})
    await message.reply_text(answer)

async def http_health(_):
    return web.json_response({"ok": True, "service": "shruti-chatbot"})

async def run():
    server = web.Application()
    server.router.add_get("/", http_health)
    server.router.add_get("/health", http_health)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    try:
        await app.start()
        me = await app.get_me()
        log.info("Telegram connected as @%s", me.username)
        await idle()
    finally:
        await runner.cleanup()
        try:
            await app.stop()
        except Exception:
            pass

def main():
    asyncio.run(run())
