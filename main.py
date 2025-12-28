import os
import asyncio
import logging
from datetime import datetime
import pytz

import discord
from discord import app_commands
from dotenv import load_dotenv

import openai
import tweepy

# ────────── 基本設定 ──────────
load_dotenv()
logging.basicConfig(level=logging.INFO)

TZ = pytz.timezone("Asia/Taipei")

# ────────── 環境變數 ──────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")

openai.api_key = OPENAI_API_KEY

# ────────── Discord Bot ──────────
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ────────── 全域狀態 ──────────
X_STATUS = {
    "login": False,
    "can_tweet": False,
    "can_media": False,
    "error": None
}

TOPICS = [
    "科技冷知識",
    "AI 小技巧",
    "程式語錄"
]

POST_TIMES = ["08:00", "12:00", "18:00", "22:00"]
PAUSED = False


# ────────── X API 初始化 ──────────
def init_x_clients():
    auth = tweepy.OAuth1UserHandler(
        X_API_KEY,
        X_API_SECRET,
        X_ACCESS_TOKEN,
        X_ACCESS_TOKEN_SECRET
    )

    api_v1 = tweepy.API(auth)
    client_v2 = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET
    )
    return api_v1, client_v2


# ────────── X API 自我檢測 ──────────
def x_api_self_check():
    global X_STATUS

    try:
        api_v1, client_v2 = init_x_clients()

        # 1️⃣ 登入測試
        me = client_v2.get_me()
        X_STATUS["login"] = True

        # 2️⃣ 發文字測試
        client_v2.create_tweet(text="(API 測試) 文字權限確認")
        X_STATUS["can_tweet"] = True

        # 3️⃣ 圖片測試（Free tier 通常會失敗）
        try:
            api_v1.media_upload("test.png")
            X_STATUS["can_media"] = True
        except Exception:
            X_STATUS["can_media"] = False

    except Exception as e:
        X_STATUS["error"] = str(e)

    logging.info(f"X API 狀態：{X_STATUS}")


# ────────── OpenAI 產文 ──────────
def generate_text(topic: str) -> str:
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "你是一個推特文案助手"},
            {"role": "user", "content": f"請寫一則關於「{topic}」的短推文"}
        ]
    )
    return resp.choices[0].message.content


# ────────── 發文（Free tier 安全版） ──────────
def post_to_x(text: str):
    if not X_STATUS["can_tweet"]:
        logging.error("❌ 無發文權限")
        return

    api_v1, client_v2 = init_x_clients()

    if X_STATUS["can_media"]:
        logging.info("（理論上）可發圖，但 Free tier 幾乎不會進來")
    else:
        logging.info("⚠️ Free tier：只發文字")

    client_v2.create_tweet(text=text)
    logging.info("✅ 推文已送出（文字）")


# ────────── 排程迴圈 ──────────
async def scheduler():
    while True:
        if not PAUSED:
            now = datetime.now(TZ).strftime("%H:%M")
            if now in POST_TIMES:
                topic = TOPICS[datetime.now().hour % len(TOPICS)]
                text = generate_text(topic)
                post_to_x(text)
                await asyncio.sleep(60)
        await asyncio.sleep(10)


# ────────── Discord 指令 ──────────
@tree.command(name="debug", description="查看系統與 X API 狀態")
async def debug(interaction: discord.Interaction):
    msg = f"""
🧪 系統偵錯
━━━━━━━━━━━━━━
🕒 時區：Asia/Taipei
⏰ 排程時間：{', '.join(POST_TIMES)}
📚 主題數：{len(TOPICS)}
⏸️ 暫停：{PAUSED}

🐦 X API
登入：{'✅' if X_STATUS['login'] else '❌'}
發文：{'✅' if X_STATUS['can_tweet'] else '❌'}
圖片：{'✅' if X_STATUS['can_media'] else '❌（Free tier）'}

⚠️ 錯誤：{X_STATUS['error']}
"""
    await interaction.response.send_message(msg, ephemeral=True)


# ────────── 啟動 ──────────
@client.event
async def on_ready():
    await tree.sync()
    x_api_self_check()
    asyncio.create_task(scheduler())
    logging.info(f"🤖 Bot 已上線：{client.user}")


client.run(DISCORD_TOKEN)
