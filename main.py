import os
import asyncio
import logging
from discord.ext import commands, tasks
import discord
import tweepy  # X API
from datetime import datetime
import pytz

# ---------- 環境變數 ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# ---------- 設定日誌 ----------
logging.basicConfig(level=logging.INFO)

# ---------- Discord Bot 設定 ----------
intents = discord.Intents.default()
intents.message_content = True  # 必須開啟才能使用 slash command
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- 推特登入 ----------
twitter_client = None
try:
    auth = tweepy.OAuth1UserHandler(
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
    )
    twitter_client = tweepy.API(auth)
    logging.info("✅ X API 登入成功")
except Exception as e:
    logging.error(f"❌ X API 登入失敗: {e}")

# ---------- 時間與主題 ----------
time_slots = ["08:00", "12:00", "18:00", "22:00"]
themes = ["AI", "Tech", "Gaming"]
paused = False
timezone = pytz.timezone("Asia/Taipei")

# ---------- 排程任務 ----------
@tasks.loop(minutes=1)
async def scheduled_post():
    global paused
    if paused:
        return
    now = datetime.now(timezone).strftime("%H:%M")
    if now in time_slots:
        try:
            message = f"今天主題: {themes}"
            if twitter_client:
                twitter_client.update_status(message)
                logging.info(f"🐦 已發文: {message}")
        except Exception as e:
            logging.error(f"❌ 發文失敗: {e}")

# ---------- Discord 指令 ----------
@bot.command()
async def addtime(ctx, time: str):
    """新增排程時間"""
    if time not in time_slots:
        time_slots.append(time)
        await ctx.send(f"✅ 新增時段: {time}")
    else:
        await ctx.send("⚠️ 時段已存在")

@bot.command()
async def removetime(ctx, time: str):
    """移除排程時間"""
    if time in time_slots:
        time_slots.remove(time)
        await ctx.send(f"✅ 移除時段: {time}")
    else:
        await ctx.send("⚠️ 時段不存在")

@bot.command()
async def time_schedule(ctx):
    """查看現有時段"""
    await ctx.send(f"🕒 時段: {', '.join(time_slots)}")

@bot.command()
async def addtheme(ctx, theme: str):
    """新增主題"""
    if theme not in themes:
        themes.append(theme)
        await ctx.send(f"✅ 新增主題: {theme}")
    else:
        await ctx.send("⚠️ 主題已存在")

@bot.command()
async def removetheme(ctx, theme: str):
    """移除主題"""
    if theme in themes:
        themes.remove(theme)
        await ctx.send(f"✅ 移除主題: {theme}")
    else:
        await ctx.send("⚠️ 主題不存在")

@bot.command()
async def theme_schedule(ctx):
    """查看主題列表"""
    await ctx.send(f"📚 主題: {', '.join(themes)}")

@bot.command()
async def debug(ctx):
    """回報狀態"""
    status = f"""
🧪 系統偵錯
━━━━━━━━━━━━━━
🕒 時區：{timezone.zone}
⏰ 排程時間：{', '.join(time_slots)}
📚 主題數：{len(themes)}
⏸️ 暫停：{paused}

🐦 X API {'✅' if twitter_client else '❌'}
"""
    await ctx.send(status)

@bot.command()
async def pause(ctx):
    """暫停排程"""
    global paused
    paused = True
    await ctx.send("⏸️ 已暫停排程")

@bot.command()
async def resume(ctx):
    """恢復排程"""
    global paused
    paused = False
    await ctx.send("▶️ 已恢復排程")

# ---------- 啟動 Bot ----------
async def main():
    try:
        scheduled_post.start()
    except Exception as e:
        logging.error(f"Scheduler 啟動失敗: {e}")

    while True:
        try:
            await bot.start(DISCORD_TOKEN)
        except Exception as e:
            logging.error(f"Bot 發生錯誤: {e}")
            await asyncio.sleep(10)  # 失敗後等待再重試

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 手動停止 Bot")
