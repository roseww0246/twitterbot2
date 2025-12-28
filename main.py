import os
import asyncio
import logging
from datetime import datetime
import random

from fastapi import FastAPI
import uvicorn

import discord
from discord.ext import commands

import tweepy
from openai import OpenAI

# =========================
# 基本設定
# =========================

logging.basicConfig(level=logging.INFO)

TZ = "Asia/Taipei"

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN 未設定")

# =========================
# OpenAI
# =========================

openai_client = None
if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logging.info("✅ OpenAI 已啟用")
else:
    logging.warning("⚠️ 未設定 OPENAI_API_KEY，跳過 AI 生成")

# =========================
# X (Twitter)
# =========================

x_client = None
try:
    if all(os.getenv(k) for k in [
        "X_API_KEY", "X_API_SECRET",
        "X_ACCESS_TOKEN", "X_ACCESS_SECRET"
    ]):
        auth = tweepy.OAuth1UserHandler(
            os.getenv("X_API_KEY"),
            os.getenv("X_API_SECRET"),
            os.getenv("X_ACCESS_TOKEN"),
            os.getenv("X_ACCESS_SECRET"),
        )
        x_client = tweepy.API(auth)
        x_client.verify_credentials()
        logging.info("✅ X API 登入成功")
    else:
        logging.warning("⚠️ X API 未完整設定")
except Exception as e:
    logging.error(f"❌ X API 初始化失敗: {e}")
    x_client = None

# =========================
# Discord Bot
# =========================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logging.info(f"✅ Discord 已登入：{bot.user}")
    try:
        await bot.tree.sync()
        logging.info("✅ Discord 指令已同步")
    except Exception as e:
        logging.error(f"❌ 指令同步失敗: {e}")


@bot.tree.command(name="debug", description="系統狀態檢測")
async def debug(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"""
🧪 系統狀態
━━━━━━━━━━━━━━
🕒 時間：{datetime.now()}
🤖 Discord：✅
🐦 X API：{"✅" if x_client else "❌"}
🎨 OpenAI：{"✅" if openai_client else "❌"}
""",
        ephemeral=True
    )

# =========================
# AI 生成內容
# =========================

async def generate_ai_post():
    if not openai_client:
        return "自動推文測試 🚀", None

    prompt = random.choice([
        "生成一則科技感十足的推文",
        "生成一則療癒風格的短推文",
        "生成一則未來感 AI 主題推文"
    ])

    text = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    ).choices[0].message.content.strip()

    image_url = None
    try:
        img = openai_client.images.generate(
            model="gpt-image-1",
            prompt="未來感 AI 插畫，科技風，乾淨背景",
            size="1024x1024"
        )
        image_url = img.data[0].url
    except Exception as e:
        logging.warning(f"圖片生成失敗（Free tier 可忽略）: {e}")

    return text, image_url

# =========================
# 發推
# =========================

async def post_to_x():
    if not x_client:
        logging.warning("⚠️ 未啟用 X，自動跳過發文")
        return

    text, image_url = await generate_ai_post()

    try:
        if image_url:
            x_client.update_status(status=text + "\n" + image_url)
        else:
            x_client.update_status(status=text)

        logging.info("🐦 已自動發推")
    except Exception as e:
        logging.error(f"❌ 發推失敗: {e}")

# =========================
# 排程（完全自動）
# =========================

async def scheduler_loop():
    schedule_hours = [8, 12, 18, 22]

    while True:
        now = datetime.now()
        if now.hour in schedule_hours and now.minute == 0:
            logging.info("⏰ 觸發排程發文")
            await post_to_x()
            await asyncio.sleep(60)

        await asyncio.sleep(20)

# =========================
# 心跳（Railway 保活）
# =========================

async def heartbeat():
    while True:
        logging.info(f"🫀 Bot 活動中... {datetime.now()}")
        await asyncio.sleep(30)

# =========================
# FastAPI（主服務）
# =========================

app = FastAPI()


@app.get("/ping")
async def ping():
    logging.info("保活心跳: 200")
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    logging.info("🚀 FastAPI 啟動，啟動背景服務")
    asyncio.create_task(bot.start(DISCORD_TOKEN))
    asyncio.create_task(heartbeat())
    asyncio.create_task(scheduler_loop())

# =========================
# 啟動點（唯一主行程）
# =========================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        log_level="info",
    )

