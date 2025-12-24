import os
import asyncio
from datetime import datetime, timedelta
import pytz
import requests
import discord
from discord.ext import commands, tasks
import tweepy
import openai
from dotenv import load_dotenv

# -------------- 環境變數 --------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

openai.api_key = OPENAI_API_KEY

# -------------- Discord Bot --------------
import discord
from discord import app_commands

intents = discord.Intents.default()
intents.message_content = True  

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)  
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()  

client = MyBot()


# -------------- Twitter Client --------------
auth = tweepy.OAuth1UserHandler(
    TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
)
twitter_client = tweepy.API(auth)

# -------------- 設定時區與排程 --------------
tz = pytz.timezone("Asia/Taipei")
# 初始時段
post_times = ["08:00", "12:00", "18:00", "22:00"]
# 初始主題
themes = ["cute animals", "meme"]

# -------------- 偵錯模式函數 --------------
async def generate_and_post():
    now = datetime.now(tz)
    print(f"⏰ 排程觸發時間: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    if not themes:
        print("⚠️ 主題列表為空，跳過發圖")
        return
    theme_prompt = themes[now.hour % len(themes)]
    print("📌 主題列表:", themes)
    print(f"📍 選擇主題: {theme_prompt}")

    # 生成圖片
    try:
        print("📍 呼叫 OpenAI 生成圖片...")
        response = openai.Image.create(prompt=theme_prompt, n=1, size="1024x1024")
        image_url = response['data'][0]['url']
        print("✅ OpenAI 圖片 URL:", image_url)
    except Exception as e:
        print("❌ OpenAI 生成失敗:", e)
        return

    # 下載圖片
    try:
        print("📍 下載圖片到本地...")
        filename = "temp.png"
        r = requests.get(image_url)
        with open(filename, "wb") as f:
            f.write(r.content)
        print("✅ 圖片下載完成")
    except Exception as e:
        print("❌ 圖片下載失敗:", e)
        return

    # 發文到 Twitter
    try:
        print("📍 發推文...")
        media = twitter_client.media_upload(filename)
        twitter_client.update_status(status=theme_prompt, media_ids=[media.media_id])
        print("✅ 推文發送成功")
    except Exception as e:
        print("❌ 發推文失敗:", e)
        return

    # 回報到 Discord
    try:
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        await channel.send(f"✅ {now.strftime('%Y-%m-%d %H:%M')} 推文完成\n主題: {theme_prompt}\nOpenAI URL: {image_url}")
        print("✅ 成效回報已送到 Discord")
    except Exception as e:
        print("❌ Discord 回報失敗:", e)

# -------------- 排程任務 --------------
@tasks.loop(minutes=1)
async def scheduler():
    now = datetime.now(tz).strftime("%H:%M")
    if now in post_times:
        print(f"🚀 時間匹配 {now}，開始發文流程")
        await generate_and_post()
    else:
        print(f"⏳ 現在時間 {now}，未到發文時段")

# -------------- Discord 指令 --------------
from discord import app_commands
import discord

intents = discord.Intents.default()
intents.message_content = True

# 全域列表
post_times = ["08:00", "12:00", "18:00", "22:00"]
themes = ["cute animals", "meme"]

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = MyBot()

# ---------- Slash Commands ----------

@client.tree.command(name="addtime", description="新增發文時段")
@app_commands.describe(time_str="時段，例如 14:00")
async def addtime(interaction: discord.Interaction, time_str: str):
    global post_times
    post_times.append(time_str)
    await interaction.response.send_message(f"✅ 新增發文時段: {time_str}")

@client.tree.command(name="removetime", description="刪除發文時段")
@app_commands.describe(time_str="時段，例如 14:00")
async def removetime(interaction: discord.Interaction, time_str: str):
    global post_times
    if time_str in post_times:
        post_times.remove(time_str)
        await interaction.response.send_message(f"✅ 刪除發文時段: {time_str}")
    else:
        await interaction.response.send_message(f"⚠️ 時段不存在: {time_str}")

@client.tree.command(name="time_schedule", description="查看現有發文時段")
async def time_schedule(interaction: discord.Interaction):
    await interaction.response.send_message(f"📅 現有發文時段: {post_times}")

@client.tree.command(name="addtheme", description="新增發文主題")
@app_commands.describe(theme="主題文字，例如 cute animals")
async def addtheme(interaction: discord.Interaction, theme: str):
    global themes
    themes.append(theme)
    await interaction.response.send_message(f"✅ 新增主題: {theme}")

@client.tree.command(name="removetheme", description="刪除發文主題")
@app_commands.describe(theme="主題文字，例如 cute animals")
async def removetheme(interaction: discord.Interaction, theme: str):
    global themes
    if theme in themes:
        themes.remove(theme)
        await interaction.response.send_message(f"✅ 刪除主題: {theme}")
    else:
        await interaction.response.send_message(f"⚠️ 主題不存在: {theme}")

@client.tree.command(name="theme_schedule", description="查看現有主題")
async def theme_schedule(interaction: discord.Interaction):
    await interaction.response.send_message(f"📌 現有主題: {themes}")

@client.tree.command(name="report", description="立即生成報告")
async def report(interaction: discord.Interaction):
    # 這裡可以呼叫你的 generate_and_post() 函數
    await interaction.response.send_message("📊 報告已生成（示範）")

# 啟動 Bot
client.run(DISCORD_BOT_TOKEN)


# -------------- 啟動 --------------
@bot.event
async def on_ready():
    print(f"🤖 Bot 已上線: {bot.user}")
    scheduler.start()

# -------------- 主程式 --------------
if __name__ == "__main__":
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except KeyboardInterrupt:
        print("🛑 手動停止 Bot")
