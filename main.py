import os
import asyncio
import logging
from datetime import datetime

import aiohttp
import discord
from discord import app_commands

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager

import uvicorn

# ======================
# 基本設定
# ======================
logging.basicConfig(level=logging.INFO)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("PORT", 8080))

# ======================
# Discord Bot
# ======================
intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    await tree.sync()
    logging.info(f"✅ Discord 已登入：{bot.user}")

@tree.command(name="debug", description="系統狀態")
async def debug(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🫀 Bot 活著\n⏰ {datetime.now()}"
    )

# ======================
# FastAPI + Lifespan
# ======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動
    logging.info("🚀 FastAPI 啟動，啟動 Discord Bot")
    discord_task = asyncio.create_task(bot.start(DISCORD_TOKEN))
    heartbeat_task = asyncio.create_task(self_ping())

    yield

    # 關閉
    logging.info("🛑 FastAPI 關閉，停止服務")
    heartbeat_task.cancel()
    await bot.close()

app = FastAPI(lifespan=lifespan)

# ======================
# HTTP
# ======================
@app.get("/ping")
async def ping():
    return PlainTextResponse("pong")

# ======================
# Railway 自我保活
# ======================
async def self_ping():
    await asyncio.sleep(10)  # 等 uvicorn 起來
    url = f"http://127.0.0.1:{PORT}/ping"

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url) as resp:
                    logging.info(f"💓 保活心跳：{resp.status}")
            except Exception as e:
                logging.error(f"心跳失敗: {e}")

            await asyncio.sleep(25)  # < 30 秒，Railway 安全值

# ======================
# 主入口
# ======================
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )

