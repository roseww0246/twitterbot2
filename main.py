import os
import asyncio
import logging
from datetime import datetime
from discord.ext import commands, tasks
import discord
import tweepy
import openai
from fastapi import FastAPI
import uvicorn
import pytz
import requests
from io import BytesIO

logging.basicConfig(level=logging.INFO)

# ---------- 環境變數 ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

TIMEZONE = pytz.timezone("Asia/Taipei")

# ---------- OpenAI 初始化 ----------
openai.api_key = OPENAI_API_KEY

# ---------- Twitter 初始化 ----------
twitter_client = None
if all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET]):
    auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
    twitter_client = tweepy.API(auth)
    try:
        twitter_client.verify_credentials()
        logging.info("✅ X API 登入成功")
    except Exception as e:
        logging.error(f"❌ X API 登入失敗: {e}")

# ---------- Discord Bot 初始化 ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- 時段與主題 ----------
time_slots = ["08:00", "12:00", "18:00", "22:00"]
themes = ["AI", "Nature", "Funny"]
paused = False

# ---------- Discord 指令 ----------
@bot.event
async def on_ready():
    logging.info(f"✅ 已登入 Discord: {bot.user}")
    if not scheduled_task.is_running():
        scheduled_task.start()

@bot.command(name="addtime")
async def add_time(ctx, time_str: str):
    if time_str not in time_slots:
        time_slots.append(time_str)
        await ctx.send(f"✅ 已增加時段: {time_str}")
    else:
        await ctx.send("⚠️ 時段已存在")

@bot.command(name="removetime")
async def remove_time(ctx, time_str: str):
    if time_str in time_slots:
        time_slots.remove(time_str)
        await ctx.send(f"✅ 已刪除時段: {time_str}")
    else:
        await ctx.send("⚠️ 時段不存在")

@bot.command(name="time_schedule")
async def time_schedule(ctx):
    await ctx.send(f"🕒 現有時段: {', '.join(time_slots)}")

@bot.command(name="addtheme")
async def add_theme(ctx, *, theme: str):
    if theme not in themes:
        themes.append(theme)
        await ctx.send(f"✅ 已增加主題: {theme}")
    else:
        await ctx.send("⚠️ 主題已存在")

@bot.command(name="removetheme")
async def remove_theme(ctx, *, theme: str):
    if theme in themes:
        themes.remove(theme)
        await ctx.send(f"✅ 已刪除主題: {theme}")
    else:
        await ctx.send("⚠️ 主題不存在")

@bot.command(name="theme_schedule")
async def theme_schedule(ctx):
    await ctx.send(f"📚 現有主題: {', '.join(themes)}")

@bot.command(name="debug")
async def debug(ctx):
    status = f"""
🧪 系統偵錯
━━━━━━━━━━━━━━
🕒 時區：{TIMEZONE.zone}
⏰ 排程時間：{', '.join(time_slots)}
📚 主題數：{len(themes)}
⏸️ 暫停：{paused}

🐦 X API
登入：{'✅' if twitter_client else '❌'}
"""
    await ctx.send(status)

@bot.command(name="pause")
async def pause(ctx):
    global paused
    paused = True
    await ctx.send("⏸️ 已暫停自動發文")

@bot.command(name="resume")
async def resume(ctx):
    global paused
    paused = False
    await ctx.send("▶️ 已恢復自動發文")

# ---------- 發文與生成圖片 ----------
async def generate_image(prompt):
    try:
        result = openai.Image.create(prompt=prompt, n=1, size="1024x1024")
        return result['data'][0]['url']
    except Exception as e:
        logging.error(f"❌ 生成圖片失敗: {e}")
        return None

async def post_to_twitter(prompt):
    if not twitter_client:
        logging.warning("❌ Twitter 尚未登入")
        return
    image_url = await generate_image(prompt)
    if image_url:
        resp = requests.get(image_url)
        img_data = BytesIO(resp.content)
        try:
            twitter_client.update_status_with_media(status=prompt, filename="image.png", file=img_data)
            logging.info("✅ 成功發文至 X")
        except Exception as e:
            logging.error(f"❌ 發文失敗: {e}")

# ---------- 排程 ----------
@tasks.loop(seconds=60)
async def scheduled_task():
    global paused
    if paused or not time_slots or not themes:
        return
    now = datetime.now(TIMEZONE)
    current_time = now.strftime("%H:%M")
    if current_time in time_slots:
        prompt = f"自動推文主題: {themes[now.minute % len(themes)]}"
        await post_to_twitter(prompt)

# ---------- FastAPI 保活 ----------
app = FastAPI()

@app.get("/ping")
async def ping():
    return {"status": "alive"}

# ---------- 主程式 ----------
async def main():
    bot_task = asyncio.create_task(bot.start(DISCORD_TOKEN))
    server_task = asyncio.create_task(
        uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)), log_level="info")
    )
    await asyncio.gather(bot_task, server_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 手動停止 Bot")
