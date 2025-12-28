import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
import sqlite3
from discord.ext import commands, tasks
import discord
import openai
import tweepy

# ====== Environment Variables ======
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ====== Logging ======
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ====== Database ======
conn = sqlite3.connect("bot_data.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hour TEXT
)""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme TEXT
)""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    tweet TEXT
)""")
conn.commit()

# ====== Discord Bot Setup ======
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ====== OpenAI Setup ======
openai.api_key = OPENAI_API_KEY

# ====== Twitter Setup ======
try:
    auth = tweepy.OAuth1UserHandler(
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
    )
    twitter_client = tweepy.API(auth)
except Exception as e:
    logging.error(f"Twitter 初始化失敗: {e}")
    twitter_client = None

# ====== Helper Functions ======
async def generate_image(prompt: str) -> str:
    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        image_url = response['data'][0]['url']
        return image_url
    except Exception as e:
        logging.error(f"生成圖片失敗: {e}")
        return None

async def post_tweet(text: str, image_url: str = None):
    if not twitter_client:
        logging.warning("Twitter 未初始化")
        return False
    try:
        if image_url:
            filename = "temp.png"
            # Download image
            import requests
            r = requests.get(image_url)
            with open(filename, "wb") as f:
                f.write(r.content)
            twitter_client.update_status_with_media(status=text, filename=filename)
        else:
            twitter_client.update_status(status=text)
        return True
    except Exception as e:
        logging.error(f"發推失敗: {e}")
        return False

# ====== Discord Commands ======
@bot.command()
async def addtime(ctx, hour: str):
    cursor.execute("INSERT INTO times (hour) VALUES (?)", (hour,))
    conn.commit()
    await ctx.send(f"✅ 已新增時段 {hour}")

@bot.command()
async def removetime(ctx, hour: str):
    cursor.execute("DELETE FROM times WHERE hour=?", (hour,))
    conn.commit()
    await ctx.send(f"🗑️ 已刪除時段 {hour}")

@bot.command()
async def time_schedule(ctx):
    cursor.execute("SELECT hour FROM times")
    times = cursor.fetchall()
    await ctx.send(f"🕒 現有時段: {', '.join(t[0] for t in times)}")

@bot.command()
async def addtheme(ctx, theme: str):
    cursor.execute("INSERT INTO themes (theme) VALUES (?)", (theme,))
    conn.commit()
    await ctx.send(f"✅ 已新增主題 {theme}")

@bot.command()
async def removetheme(ctx, theme: str):
    cursor.execute("DELETE FROM themes WHERE theme=?", (theme,))
    conn.commit()
    await ctx.send(f"🗑️ 已刪除主題 {theme}")

@bot.command()
async def theme_schedule(ctx):
    cursor.execute("SELECT theme FROM themes")
    themes = cursor.fetchall()
    await ctx.send(f"📚 現有主題: {', '.join(t[0] for t in themes)}")

@bot.command()
async def report(ctx):
    cursor.execute("SELECT timestamp, tweet FROM reports ORDER BY id DESC LIMIT 5")
    reports = cursor.fetchall()
    msg = "\n".join([f"{t[0]}: {t[1]}" for t in reports])
    await ctx.send(f"📊 最新報告:\n{msg}")

@bot.command()
async def debug(ctx):
    await ctx.send(f"🧪 Bot 活動中\nDiscord Token={'✅' if DISCORD_TOKEN else '❌'}\nTwitter={'✅' if twitter_client else '❌'}\nOpenAI={'✅' if OPENAI_API_KEY else '❌'}")

# ====== Scheduler Loop ======
@tasks.loop(minutes=1)
async def scheduler_loop():
    now = datetime.now(timezone(timedelta(hours=8)))
    cursor.execute("SELECT hour FROM times")
    hours = [t[0] for t in cursor.fetchall()]
    if now.strftime("%H:%M") in hours:
        cursor.execute("SELECT theme FROM themes")
        themes = [t[0] for t in cursor.fetchall()]
        if not themes:
            logging.warning("沒有主題，跳過發文")
            return
        theme = themes[now.minute % len(themes)]  # 隨機選一個
        prompt = f"{theme}"
        image_url = await generate_image(prompt)
        tweet_text = f"{theme} #{now.strftime('%Y-%m-%d %H:%M')}"
        success = await post_tweet(tweet_text, image_url)
        cursor.execute("INSERT INTO reports (timestamp, tweet) VALUES (?,?)", (now.isoformat(), tweet_text))
        conn.commit()
        logging.info(f"✅ 已發文: {tweet_text}, 成功: {success}")

# ====== Heartbeat Loop ======
@tasks.loop(minutes=1)
async def heartbeat():
    logging.info(f"🫀 Bot 活動中... {datetime.now(timezone(timedelta(hours=8)))}")

# ====== Bot Startup ======
async def main():
    heartbeat.start()
    scheduler_loop.start()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 手動停止 Bot")
