import os
import discord
from discord.ext import commands
from fastapi import FastAPI
import uvicorn
import asyncio
import openai
import logging

# ----------------- 設定 -----------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", 8080))

if not DISCORD_TOKEN or not OPENAI_API_KEY:
    raise ValueError("請確認環境變數 DISCORD_TOKEN 與 OPENAI_API_KEY 已設定")

openai.api_key = OPENAI_API_KEY

intents = discord.Intents.default()
intents.message_content = True  # 確保可以讀取訊息內容

bot = commands.Bot(command_prefix="/", intents=intents)
app = FastAPI()
logging.basicConfig(level=logging.INFO)

# ----------------- Discord 指令 -----------------
@bot.slash_command(name="make_picture", description="生成圖片並回傳到頻道")
async def make_picture(ctx: discord.ApplicationContext, prompt: str):
    await ctx.respond("🖌️ 開始生成圖片，請稍候...")
    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="512x512"
        )
        image_url = response['data'][0]['url']
        await ctx.send(f"✅ 圖片生成完成：{image_url}")
    except openai.error.OpenAIError as e:
        await ctx.send(f"❌ 生成圖片時出錯：{e}")

# ----------------- FastAPI 保活 -----------------
@app.get("/ping")
async def ping():
    return {"status": "ok"}

# ----------------- 啟動函數 -----------------
async def start_bot():
    await bot.start(DISCORD_TOKEN)

async def main():
    # 建立 Discord Bot 任務
    bot_task = asyncio.create_task(start_bot())
    # 啟動 FastAPI
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    # 等待兩個任務結束（實際上會常駐）
    await asyncio.gather(bot_task, server_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot 停止運行")
