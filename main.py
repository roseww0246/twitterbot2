import os
import discord
from discord.ext import commands
import openai
import asyncio

# 設定環境變數
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DISCORD_TOKEN or not OPENAI_API_KEY:
    raise ValueError("請確認已設定 DISCORD_TOKEN 和 OPENAI_API_KEY 環境變數")

openai.api_key = OPENAI_API_KEY

# Discord intents
intents = discord.Intents.default()
intents.message_content = True  # 讓 Bot 可以讀取訊息內容

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"✅ 已登入 Discord: {bot.user}")
    print("🫀 Bot 待命中...")

# /make_picture 指令
@bot.command(name="make_picture")
async def make_picture(ctx, *, prompt: str):
    """
    使用 OpenAI 生成圖片並回傳至 Discord 頻道
    """
    await ctx.send(f"🎨 開始生成圖片: {prompt}")
    try:
        response = openai.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )
        image_url = response.data[0].url
        await ctx.send(f"🖼️ 生成完成: {image_url}")
    except openai.error.OpenAIError as e:
        # 處理額度用盡
        if hasattr(e, "http_status") and e.http_status == 400 and "billing_hard_limit_reached" in str(e):
            await ctx.send("⚠️ 生成失敗：帳號額度已用完，請檢查 OpenAI 帳號。")
        else:
            await ctx.send(f"❌ 生成圖片失敗: {e}")

# 保活心跳（Railway friendly）
async def keep_alive():
    while True:
        print("💓 Bot 保活心跳...")
        await asyncio.sleep(300)  # 每 5 分鐘印一次訊息

async def main():
    async with bot:
        bot.loop.create_task(keep_alive())
        await bot.start(DISCORD_TOKEN)

# 啟動 Bot
if __name__ == "__main__":
    asyncio.run(main())
