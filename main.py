import os
import discord
from discord.ext import commands
import openai
import aiohttp
import asyncio
import logging

# ---------- 設定日誌 ----------
logging.basicConfig(level=logging.INFO)

# ---------- 環境變數 ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "1234567890"))  # 改成你的頻道ID

if not DISCORD_TOKEN or not OPENAI_API_KEY:
    raise Exception("請確認 DISCORD_TOKEN 和 OPENAI_API_KEY 已經設定")

openai.api_key = OPENAI_API_KEY

# ---------- Discord Bot 設定 ----------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- Bot 事件 ----------
@bot.event
async def on_ready():
    logging.info(f"✅ 已登入 Discord: {bot.user}")
    logging.info("🫀 Bot 待命中...")

# ---------- /make picture 指令 ----------
@bot.slash_command(name="make picture", description="生成圖片並回傳到頻道")
async def make_picture(ctx, *, prompt: str):
    """使用 OpenAI 生成圖片並回傳 Discord"""
    await ctx.respond(f"🎨 收到請求，生成圖片中: `{prompt}`", ephemeral=True)
    
    try:
        response = await openai.images.generate(
            model="gpt-image-1",  # 最新圖片生成模型
            prompt=prompt,
            size="1024x1024"
        )

        image_url = response.data[0].url
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(f"🖼️ 生成完成: `{prompt}`\n{image_url}")
        else:
            await ctx.followup.send("⚠️ 找不到指定頻道，請檢查 CHANNEL_ID")
    except Exception as e:
        logging.error(f"生成圖片失敗: {e}")
        await ctx.followup.send(f"❌ 生成圖片失敗: {e}")

# ---------- 保活 (適用 Railway) ----------
async def keep_alive():
    from fastapi import FastAPI
    import uvicorn

    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"status": "ok"}

    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)), log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

# ---------- 主程式 ----------
async def main():
    await asyncio.gather(
        bot.start(DISCORD_TOKEN),
        keep_alive()
    )

if __name__ == "__main__":
    asyncio.run(main())
