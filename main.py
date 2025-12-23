import os
import asyncio
import random
import sqlite3
import schedule
import requests
import traceback
from datetime import datetime, timedelta

import discord
from discord import app_commands
import tweepy
from dotenv import load_dotenv
from openai import OpenAI

# =========================
# 基本設定
# =========================
load_dotenv()

RUNNING = True
ERROR_COUNT = 0
MAX_ERRORS = 5

# =========================
# API Client
# =========================
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

twitter = tweepy.Client(
    bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
    consumer_key=os.getenv("TWITTER_API_KEY"),
    consumer_secret=os.getenv("TWITTER_API_SECRET"),
    access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
    access_token_secret=os.getenv("TWITTER_ACCESS_SECRET"),
)

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# =========================
# SQLite
# =========================
db = sqlite3.connect("bot.db", check_same_thread=False)
cur = db.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS timeslots (time TEXT PRIMARY KEY)")
cur.execute("""
CREATE TABLE IF NOT EXISTS themes (
    time TEXT,
    theme TEXT,
    success INTEGER DEFAULT 1,
    failure INTEGER DEFAULT 1,
    PRIMARY KEY (time, theme)
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS posts (
    tweet_id TEXT,
    time TEXT,
    theme TEXT,
    created_at TEXT
)
""")
db.commit()

# =========================
# 工具
# =========================
def record_error(e):
    global ERROR_COUNT, RUNNING
    ERROR_COUNT += 1
    print("[ERROR]", e)
    if ERROR_COUNT >= MAX_ERRORS:
        RUNNING = False
        print("🛑 自動停機（錯誤過多）")

def load_times():
    cur.execute("SELECT time FROM timeslots ORDER BY time")
    return [r[0] for r in cur.fetchall()]

def load_themes(time):
    cur.execute("SELECT theme, success, failure FROM themes WHERE time=?", (time,))
    return cur.fetchall()

def choose_theme(time):
    rows = load_themes(time)
    if not rows:
        defaults = ["cute animal illustration", "funny animal meme"]
        for d in defaults:
            cur.execute("INSERT OR IGNORE INTO themes VALUES (?, ?, 1, 1)", (time, d))
        db.commit()
        rows = load_themes(time)

    samples = {
        theme: random.betavariate(success, failure)
        for theme, success, failure in rows
    }
    return max(samples, key=samples.get)

def generate_image(prompt):
    try:
        img = openai_client.images.generate(
            model="gpt-image-1",
            prompt=f"cute, viral, {prompt}",
            size="1024x1024"
        )
        url = img.data[0].url
        return requests.get(url, timeout=20).content
    except Exception as e:
        record_error(e)
        return None

# =========================
# 發文
# =========================
def post_image(time):
    if not RUNNING:
        return
    try:
        theme = choose_theme(time)
        img = generate_image(theme)
        if not img:
            return

        with open("post.png", "wb") as f:
            f.write(img)

        media = twitter.media_upload("post.png")
        tweet = twitter.create_tweet(
            text=f"🐾 {theme}",
            media_ids=[media.media_id]
        )

        cur.execute(
            "INSERT INTO posts VALUES (?, ?, ?, ?)",
            (tweet.data["id"], time, theme, datetime.utcnow().isoformat())
        )
        db.commit()

        print(f"✅ 發文成功 {time} | {theme}")

    except Exception:
        print(traceback.format_exc())

# =========================
# 分析 & 學習
# =========================
def analyze_and_learn():
    now = datetime.utcnow()
    cur.execute("SELECT * FROM posts")
    for tweet_id, time, theme, created_at in cur.fetchall():
        if now - datetime.fromisoformat(created_at) < timedelta(hours=24):
            continue

        try:
            metrics = twitter.get_tweet(
                tweet_id,
                tweet_fields=["public_metrics"]
            ).data.public_metrics

            score = metrics["like_count"] + metrics["retweet_count"] * 2
            col = "success" if score >= 10 else "failure"

            cur.execute(
                f"UPDATE themes SET {col}={col}+1 WHERE time=? AND theme=?",
                (time, theme)
            )
            cur.execute("DELETE FROM posts WHERE tweet_id=?", (tweet_id,))
            db.commit()

        except Exception as e:
            record_error(e)

def build_report():
    lines = ["📊 成效報告"]
    for t in load_times():
        lines.append(f"\n🕒 {t}")
        for theme, s, f in load_themes(t):
            rate = round(s / (s + f), 2)
            lines.append(f"- {theme} | 成功率 {rate}")
    return "\n".join(lines)

async def send_report():
    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(build_report())

# =========================
# 排程
# =========================
def setup_schedule():
    schedule.clear()
    for t in load_times():
        schedule.every().day.at(t).do(post_image, t)
    schedule.every().hour.do(analyze_and_learn)
    schedule.every().day.at("23:00").do(
        lambda: asyncio.create_task(send_report())
    )

async def scheduler_loop():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

# =========================
# Discord 指令
# =========================
@tree.command(name="addtime", description="新增發文時段")
async def addtime(interaction: discord.Interaction, time: str):
    cur.execute("INSERT OR IGNORE INTO timeslots VALUES (?)", (time,))
    db.commit()
    setup_schedule()
    await interaction.response.send_message(f"✅ 已新增 {time}")

@tree.command(name="removetime", description="刪除發文時段")
async def removetime(interaction: discord.Interaction, time: str):
    cur.execute("DELETE FROM timeslots WHERE time=?", (time,))
    cur.execute("DELETE FROM themes WHERE time=?", (time,))
    db.commit()
    setup_schedule()
    await interaction.response.send_message(f"🗑️ 已刪除 {time}")

@tree.command(name="time_schedule", description="查看發文時段")
async def time_schedule(interaction: discord.Interaction):
    await interaction.response.send_message("\n".join(load_times()))

@tree.command(name="addtheme", description="新增主題")
async def addtheme(interaction: discord.Interaction, time: str, theme: str):
    cur.execute("INSERT OR IGNORE INTO themes VALUES (?, ?, 1, 1)", (time, theme))
    db.commit()
    await interaction.response.send_message("✅ 主題已新增")

@tree.command(name="removetheme", description="刪除主題")
async def removetheme(interaction: discord.Interaction, time: str, theme: str):
    cur.execute("DELETE FROM themes WHERE time=? AND theme=?", (time, theme))
    db.commit()
    await interaction.response.send_message("🗑️ 主題已刪除")

@tree.command(name="theme_schedule", description="查看主題成效")
async def theme_schedule(interaction: discord.Interaction):
    await interaction.response.send_message(build_report())

@tree.command(name="stop", description="停止系統")
async def stop(interaction: discord.Interaction):
    global RUNNING
    RUNNING = False
    await interaction.response.send_message("🛑 已停止")

@tree.command(name="resume", description="恢復系統")
async def resume(interaction: discord.Interaction):
    global RUNNING, ERROR_COUNT
    RUNNING = True
    ERROR_COUNT = 0
    await interaction.response.send_message("▶️ 已恢復")

@tree.command(name="report", description="即時成效報告")
async def report(interaction: discord.Interaction):
    await interaction.response.send_message(build_report())

# =========================
# 啟動
# =========================
@client.event
async def setup_hook():
    setup_schedule()
    asyncio.create_task(scheduler_loop())

@client.event
async def on_ready():
    await tree.sync()
    print("✅ Bot 已啟動")

if __name__ == "__main__":
    try:
        client.run(os.getenv("DISCORD_BOT_TOKEN"))
    except KeyboardInterrupt:
        print("🛑 手動停止 Bot")