import os
import asyncio
import logging
from datetime import datetime
from discord.ext import commands, tasks
import discord
import tweepy
import openai
import pytz

# -------------------------
# 初始化 Logging
# -------------------------
logging.basicConfig(level=logging.INFO)

# -------------------------
# 環境變數
# -------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([DISCORD_TOKEN, X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET, OPENAI_API_KEY]):
    logging.error("❌ 請確認所有環境變數都已設定")
    exit(1)

openai.api_key = OPENAI_API_KEY

# -------------------------
# Tweepy X API 初始化
# -------------------------
try:
    auth = tweepy.OAuth1UserHandler(
        X_API_KEY, X_API_SECRET,
        X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
    )
    twitter_api = tweepy.API(auth)
    twitter_api.verify_credentials()
    logging.info("✅ X API 登入成功")
except Exception as e:
    logging.error(f"❌ X API 登入失敗: {e}")
    twitter_api = None

# -------------------------
# Discord Bot 初始化
# -------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# -------------------------
# Scheduler 變數
# -------------------------
post_times = ["08:00", "12:00", "18:00", "22:00"]
themes = ["可愛動物", "迷因", "熱門主題"]

paused = False

# -------------------------
# 工具函數
# -------------------------
def get_current_time():
    tz = pytz.timezone("Asia/Taipei")
    return datetime.now(tz).strftime("%H:%M")

async def post_to_twitter(theme):
    if twitter_api is None:
        logging.warning("❌ X API 未登入，跳過發文")
        return

    try:
        # 生成圖片 (OpenAI API)
        response = openai.Image.create(
            prompt=f"{theme}, cute style, trending",
            n=1,
            size="512x512"
        )
        img_url = response['data'][0]['url']

        # Twitter 發文
        twitter_api.update_status(status=f"今日主題: {theme}\n#BotTest\n{img_url}")
        logging.info(f"✅ 已發文主題: {theme}")
    except Exception as e:
        logging.error(f"❌ 發文失敗: {e}")

# -------------------------
# Discord 指令
# -------------------------
@bot.command(description="增加發文時段")
async def addtime(ctx, time: str):
    if time not in post_times:
        post_times.append(time)
        await ctx.send(f"✅ 已增加時段: {time}")
    else:
        await ctx.send("⚠️ 時段已存在")

@bot.command(description="刪除發文時段")
async def removetime(ctx, time: str):
    if time in post_times:
        post_times.remove(time)
        await ctx.send(f"✅ 已刪除時段: {time}")
    else:
        await ctx.send("⚠️ 時段不存在")

@bot.command(description="查看現有發文時段")
async def time_schedule(ctx):
    await ctx.send(f"🕒 目前時段: {', '.join(post_times)}")

@bot.command(description="增加主題")
async def addtheme(ctx, *, theme: str):
    if theme not in themes:
        themes.append(theme)
        await ctx.send(f"✅ 已增加主題: {theme}")
    else:
        await ctx.send("⚠️ 主題已存在")

@bot.command(description="刪除主題")
async def removetheme(ctx, *, theme: str):
    if theme in themes:
        themes.remove(theme)
        await ctx.send(f"✅ 已刪除主題: {theme}")
    else:
        await ctx.send("⚠️ 主題不存在")

@bot.command(description="查看現有主題")
async def theme_schedule(ctx):
    await ctx.send(f"📚 目前主題: {', '.join(themes)}")

@bot.command(description="暫停自動發文")
async def stop(ctx):
    global paused
    paused = True
    await ctx.send("⏸️ 已暫停自動發文")

@bot.command(description="恢復自動發文")
async def resume(ctx):
    global paused
    paused = False
    await ctx.send("▶️ 已恢復自動發文")

@bot.command(description="顯示系統偵錯")
async def debug(ctx):
    msg = f"""
🧪 系統偵錯
━━━━━━━━━━━━━━
🕒 時區：Asia/Taipei
⏰ 排程時間：{', '.join(post_times)}
📚 主題數：{len(themes)}
⏸️ 暫停：{paused}

🐦 X API
登入：{"✅" if twitter_api else "❌"}
發文：{"✅" if twitter_api else "❌"}
圖片：✅ (OpenAI)

"""
    await ctx.send(msg)

# -------------------------
# 自動排程任務
# -------------------------
@tasks.loop(seconds=30)
async def scheduler():
    if paused or twitter_api is None:
        return
    now = get_current_time()
    for t in post_times:
        if now == t:
            theme = themes[0]  # 簡單示範：選第一個主題
            await post_to_twitter(theme)

@scheduler.before_loop
async def before_scheduler():
    await bot.wait_until_ready()
    logging.info("⌛ Scheduler 已啟動")

# -------------------------
# 主程式
# -------------------------
scheduler.start()

try:
    bot.run(DISCORD_TOKEN)
except discord.errors.HTTPException as e:
    logging.error(f"❌ Discord 連線失敗: {e}")
except KeyboardInterrupt:
    logging.info("🛑 手動停止 Bot")
