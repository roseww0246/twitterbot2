# main.py
import os
import asyncio
import sqlite3
from datetime import datetime, timedelta
import logging

import discord
from discord.ext import commands, tasks

import openai
# 假設你用 tweepy 或其他 X API 套件
import tweepy

# ---------- 環境變數 ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")

# ---------- 日誌 ----------
logging.basicConfig(level=logging.INFO)

# ---------- SQLite ----------
conn = sqlite3.connect("bot_data.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS timeslots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hour INTEGER
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT,
    theme TEXT,
    hour INTEGER,
    likes INTEGER,
    retweets INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS bot_status (
    id INTEGER PRIMARY KEY CHECK (id=1),
    paused INTEGER DEFAULT 0
)
""")
conn.commit()

# ---------- Discord Bot ----------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- X API Setup ----------
try:
    auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET)
    api = tweepy.API(auth)
    X_OK = True
except Exception as e:
    logging.error(f"X API 初始化失敗: {e}")
    X_OK = False

# ---------- OpenAI Setup ----------
openai.api_key = OPENAI_API_KEY

# ---------- 輔助函式 ----------
def get_timeslots():
    c.execute("SELECT hour FROM timeslots")
    return [row[0] for row in c.fetchall()]

def get_themes():
    c.execute("SELECT theme FROM themes")
    return [row[0] for row in c.fetchall()]

def is_paused():
    c.execute("SELECT paused FROM bot_status WHERE id=1")
    row = c.fetchone()
    return bool(row[0]) if row else False

def set_paused(value: bool):
    c.execute("INSERT OR REPLACE INTO bot_status (id, paused) VALUES (1, ?)", (1 if value else 0,))
    conn.commit()

# ---------- Discord 指令 ----------
@bot.command(name="addtime", help="增加發文時段 (小時 0~23)")
async def addtime(ctx, hour: int):
    if 0 <= hour <= 23:
        c.execute("INSERT INTO timeslots (hour) VALUES (?)", (hour,))
        conn.commit()
        await ctx.send(f"✅ 已增加發文時段 {hour}:00")
    else:
        await ctx.send("❌ 小時請輸入 0~23")

@bot.command(name="removetime", help="刪除發文時段 (小時 0~23)")
async def removetime(ctx, hour: int):
    c.execute("DELETE FROM timeslots WHERE hour=?", (hour,))
    conn.commit()
    await ctx.send(f"✅ 已刪除發文時段 {hour}:00")

@bot.command(name="time_schedule", help="查看現有發文時段")
async def time_schedule(ctx):
    slots = get_timeslots()
    await ctx.send(f"🕒 現有發文時段: {slots}")

@bot.command(name="addtheme", help="增加主題")
async def addtheme(ctx, *, theme: str):
    c.execute("INSERT INTO themes (theme) VALUES (?)", (theme,))
    conn.commit()
    await ctx.send(f"✅ 已增加主題: {theme}")

@bot.command(name="removetheme", help="刪除主題")
async def removetheme(ctx, *, theme: str):
    c.execute("DELETE FROM themes WHERE theme=?", (theme,))
    conn.commit()
    await ctx.send(f"✅ 已刪除主題: {theme}")

@bot.command(name="theme_schedule", help="查看現有主題")
async def theme_schedule(ctx):
    themes = get_themes()
    await ctx.send(f"📚 現有主題: {themes}")

@bot.command(name="stop", help="暫停自動發文")
async def stop(ctx):
    set_paused(True)
    await ctx.send("⏸️ 已暫停自動發文")

@bot.command(name="resume", help="恢復自動發文")
async def resume(ctx):
    set_paused(False)
    await ctx.send("▶️ 已恢復自動發文")

@bot.command(name="report", help="回報今日貼文數據")
async def report(ctx):
    c.execute("SELECT * FROM stats ORDER BY timestamp DESC LIMIT 10")
    rows = c.fetchall()
    msg = "📊 最近貼文數據:\n" + "\n".join([str(row) for row in rows])
    await ctx.send(msg)

@bot.command(name="debug", help="偵測 X API 與排程狀態")
async def debug(ctx):
    msg = f"""
🧪 系統偵錯
━━━━━━━━━━━━━━
🕒 時區：Asia/Taipei
⏰ 排程時間：{get_timeslots()}
📚 主題數：{len(get_themes())}
⏸️ 暫停：{is_paused()}

🐦 X API: {"✅" if X_OK else "❌"}
"""
    await ctx.send(msg)

# ---------- 發文排程 ----------
@tasks.loop(minutes=1)
async def scheduler():
    if is_paused():
        return
    now = datetime.now()
    hour_now = now.hour
    minute_now = now.minute
    if minute_now != 0:
        return  # 每小時整點發文

    timeslots = get_timeslots()
    themes = get_themes()
    if hour_now in timeslots and themes:
        theme = themes[hour_now % len(themes)]  # 簡單 Bandit/Thompson Sampling 可替換
        try:
            # ---------- OpenAI 生成圖片 ----------
            response = openai.Image.create(
                prompt=theme,
                n=1,
                size="512x512"
            )
            image_url = response['data'][0]['url']
            # ---------- 發文到 X ----------
            if X_OK:
                api.update_status(status=f"{theme}", media_ids=[api.media_upload(image_url).media_id])
            # ---------- 儲存數據 ----------
            c.execute("INSERT INTO stats (tweet_id, theme, hour, likes, retweets) VALUES (?, ?, ?, ?, ?)",
                      ("dummy_id", theme, hour_now, 0, 0))
            conn.commit()
            logging.info(f"✅ 發文成功: {theme}")
        except Exception as e:
            logging.error(f"❌ 發文失敗: {e}")

# ---------- Bot 啟動 ----------
@bot.event
async def on_ready():
    logging.info(f"已登入 Discord: {bot.user}")
    scheduler.start()

# ---------- Main ----------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
