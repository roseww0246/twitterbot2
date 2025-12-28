import os
import asyncio
import random
import logging
from datetime import datetime, timedelta
import pytz

import discord
from discord import app_commands
from dotenv import load_dotenv

import tweepy
from openai import OpenAI

# ======================
# 基本設定
# ======================
load_dotenv()
logging.basicConfig(level=logging.INFO)

TZ = pytz.timezone("Asia/Taipei")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ======================
# 安全檢查
# ======================
if not all([DISCORD_TOKEN, DISCORD_CHANNEL_ID, OPENAI_API_KEY]):
    raise RuntimeError("❌ 環境變數未設定完整")

# ======================
# OpenAI Client (API)
# ======================
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ======================
# Twitter Client (API)
# ======================
twitter_client = tweepy.Client(
    consumer_key=os.getenv("TWITTER_API_KEY"),
    consumer_secret=os.getenv("TWITTER_API_SECRET"),
    access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
    access_token_secret=os.getenv("TWITTER_ACCESS_SECRET")
)

# ======================
# 狀態資料（之後可換 SQLite）
# ======================
post_times = ["08:00", "12:00", "18:00", "22:00"]
themes = ["可愛動物", "迷因"]
paused = False
last_post_time = {}

# ======================
# Discord Bot
# ======================
intents = discord.Intents.default()

class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        self.bg_task = asyncio.create_task(post_scheduler())
        logging.info("✅ Slash commands synced")

bot = Bot()

# ======================
# 工具函數
# ======================
def now_str():
    return datetime.now(TZ).strftime("%H:%M")

async def send_dc(msg: str):
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(msg)

# ======================
# OpenAI 圖片生成（API）
# ======================
async def generate_image(theme: str) -> str:
    logging.info(f"🎨 生成圖片主題：{theme}")
    result = openai_client.images.generate(
        model="gpt-image-1",
        prompt=f"{theme}，高品質，適合社群媒體",
        size="1024x1024"
    )
    image_url = result.data[0].url
    return image_url

# ======================
# 發推文（API）
# ======================
async def post_to_twitter(image_url: str, text: str):
    twitter_client.create_tweet(
        text=text + "\n" + image_url
    )

# ======================
# 排程核心（非阻塞）
# ======================
async def post_scheduler():
    await bot.wait_until_ready()
    logging.info("🕒 排程啟動")

    while not bot.is_closed():
        try:
            if paused:
                await asyncio.sleep(30)
                continue

            now = now_str()

            if now in post_times:
                last = last_post_time.get(now)
                if not last or datetime.now(TZ) - last > timedelta(minutes=59):
                    theme = random.choice(themes)
                    image_url = await generate_image(theme)
                    await post_to_twitter(image_url, f"{theme} 時間到！")
                    last_post_time[now] = datetime.now(TZ)
                    await send_dc(f"✅ 已發文：{now}｜主題：{theme}")

            await asyncio.sleep(30)

        except Exception as e:
            logging.exception("❌ 排程錯誤")
            await send_dc(f"❌ 排程錯誤：{e}")
            await asyncio.sleep(60)

# ======================
# Slash Commands
# ======================
@bot.tree.command(name="addtime", description="新增發文時段（HH:MM）")
async def addtime(interaction: discord.Interaction, time: str):
    post_times.append(time)
    await interaction.response.send_message(f"✅ 已新增時段 {time}")

@bot.tree.command(name="removetime", description="刪除發文時段")
async def removetime(interaction: discord.Interaction, time: str):
    if time in post_times:
        post_times.remove(time)
        await interaction.response.send_message(f"🗑️ 已刪除 {time}")
    else:
        await interaction.response.send_message("⚠️ 找不到該時段")

@bot.tree.command(name="time_schedule", description="查看所有發文時段")
async def time_schedule(interaction: discord.Interaction):
    await interaction.response.send_message(f"🕒 發文時段：{post_times}")

@bot.tree.command(name="addtheme", description="新增主題")
async def addtheme(interaction: discord.Interaction, theme: str):
    themes.append(theme)
    await interaction.response.send_message(f"🎨 新增主題：{theme}")

@bot.tree.command(name="removetheme", description="刪除主題")
async def removetheme(interaction: discord.Interaction, theme: str):
    if theme in themes:
        themes.remove(theme)
        await interaction.response.send_message(f"🗑️ 已刪除主題 {theme}")
    else:
        await interaction.response.send_message("⚠️ 找不到主題")

@bot.tree.command(name="theme_schedule", description="查看主題列表")
async def theme_schedule(interaction: discord.Interaction):
    await interaction.response.send_message(f"📌 主題：{themes}")

@bot.tree.command(name="stop", description="暫停自動發文")
async def stop(interaction: discord.Interaction):
    global paused
    paused = True
    await interaction.response.send_message("⏸️ 已暫停")

@bot.tree.command(name="resume", description="恢復自動發文")
async def resume(interaction: discord.Interaction):
    global paused
    paused = False
    await interaction.response.send_message("▶️ 已恢復")

@bot.tree.command(name="report", description="立即回傳狀態")
async def report(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"📊 狀態\n時段：{post_times}\n主題：{themes}\n暫停：{paused}"
    )

# ======================
# 啟動（唯一正確）
# ======================
if __name__ == "__main__":
    logging.info("🚀 Bot starting")
    bot.run(DISCORD_TOKEN)
