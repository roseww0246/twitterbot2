import os
import asyncio
import logging
from datetime import datetime
import pytz

import aiohttp
import discord
from discord import app_commands

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager

import uvicorn
import tweepy
from openai import OpenAI

# ======================
# 基本設定
# ======================
logging.basicConfig(level=logging.INFO)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

PORT = int(os.getenv("PORT", 8080))
TZ = pytz.timezone(os.getenv("TIMEZONE", "Asia/Taipei"))

POST_TIMES = ["08:00", "12:00", "18:00", "22:00"]
THEMES = ["可愛動物", "迷因", "療癒"]

paused = False

# ======================
# Discord
# ======================
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    await tree.sync()
    logging.info(f"✅ Discord 已登入：{bot.user}")

# ======================
# Slash Commands
# ======================
@tree.command(name="debug", description="系統狀態")
async def debug(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"""🧪 系統狀態
⏰ {datetime.now(TZ)}
⏸ 暫停：{paused}
📅 時段：{", ".join(POST_TIMES)}
🎨 主題數：{len(THEMES)}"""
    )

@tree.command(name="stop", description="暫停自動發文")
async def stop(interaction: discord.Interaction):
    global paused
    paused = True
    await interaction.response.send_message("⏸ 已暫停")

@tree.command(name="resume", description="恢復自動發文")
async def resume(interaction: discord.Interaction):
    global paused
    paused = False
    await interaction.response.send_message("▶️ 已恢復")

# ======================
# OpenAI 圖片生成
# ======================
openai_client = OpenAI(api_key=OPENAI_KEY)

async def generate_image(theme):
    prompt = f"可愛風格插畫，主題是：{theme}"
    try:
        result = openai_client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )
        return result.data[0].url
    except Exception as e:
        logging.error(f"❌ OpenAI 生成失敗: {e}")
        return None

# ======================
# X API
# ======================
def get_x_client():
    try:
        auth = tweepy.OAuth1UserHandler(
            X_API_KEY, X_API_SECRET,
            X_ACCESS_TOKEN, X_ACCESS_SECRET
        )
        return tweepy.API(auth)
    except Exception as e:
        logging.error(f"❌ X API 初始化失敗: {e}")
        return None

# ======================
# 發文流程
# ======================
async def post_to_x():
    if paused:
        return

    now = datetime.now(TZ).strftime("%H:%M")
    if now not in POST_TIMES:
        return

    theme = THEMES[now.__hash__() % len(THEMES)]
    img_url = await generate_image(theme)

    api = get_x_client()
    if not api:
        return

    text = f"{theme} 🐾"

    try:
        # Free tier 偵測
        if img_url:
            api.update_status(status=text + "\n" + img_url)
        else:
            api.update_status(status=text)

        logging.info("✅ 推文成功")

        # Discord 回報
        for guild in bot.guilds:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    await channel.send(f"🐦 已發推文：{text}")
                    return

    except Exception as e:
        logging.error(f"❌ 發文失敗: {e}")

# ======================
# 排程 Loop
# ======================
async def scheduler():
    while True:
        try:
            await post_to_x()
        except Exception as e:
            logging.error(f"Scheduler error: {e}")
        await asyncio.sleep(60)

# ======================
# Railway 自我保活
# ======================
async def self_ping():
    await asyncio.sleep(10)
    url = f"http://127.0.0.1:{PORT}/ping"
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url):
                    logging.info("💓 保活")
            except:
                pass
            await asyncio.sleep(25)

# ======================
# FastAPI Lifespan
# ======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("🚀 啟動服務")

    tasks = [
        asyncio.create_task(bot.start(DISCORD_TOKEN)),
        asyncio.create_task(self_ping()),
        asyncio.create_task(scheduler())
    ]

    yield

    for t in tasks:
        t.cancel()
    await bot.close()

app = FastAPI(lifespan=lifespan)

@app.get("/ping")
async def ping():
    return PlainTextResponse("pong")

# ======================
# Main
# ======================
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)
