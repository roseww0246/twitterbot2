import os
import discord
from discord import app_commands
from discord.ext import commands
import openai
import io
import asyncio
import logging

# -------------------------
# 基本設定
# -------------------------
logging.basicConfig(level=logging.INFO)
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

openai.api_key = os.getenv("OPENAI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN or not openai.api_key:
    logging.error("請確認 DISCORD_TOKEN 和 OPENAI_API_KEY 已設定在環境變數中！")
    raise SystemExit(1)

# -------------------------
# Bot 事件
# -------------------------
@bot.event
async def on_ready():
    await tree.sync()
    logging.info(f"✅ Discord 已登入：{bot.user}")
    logging.info("🫀 Bot 正在待命...")

# -------------------------
# /make picture 指令
# -------------------------
@tree.command(name="make_picture", description="生成圖片並回傳到 Discord")
@app_commands.describe(prompt="請輸入圖片描述")
async def make_picture(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    logging.info(f"🖼️ 收到生成圖片請求: {prompt}")
    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        image_url = response['data'][0]['url']
        
        # 下載圖片並回傳
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    await interaction.followup.send("❌ 無法下載圖片")
                    return
                data = io.BytesIO(await resp.read())
                file = discord.File(fp=data, filename="image.png")
                await interaction.followup.send(file=file)
        logging.info("✅ 圖片已回傳")
    except Exception as e:
        logging.error(f"❌ 生成圖片失敗: {e}")
        await interaction.followup.send(f"❌ 生成圖片失敗: {e}")

# -------------------------
# /debug 指令
# -------------------------
@tree.command(name="debug", description="檢查 Bot 與 OpenAI API 狀態")
async def debug(interaction: discord.Interaction):
    status = f"🫀 Bot 已登入：{bot.user}\n"
    # 測試 OpenAI 連線
    try:
        openai.Engine.list()
        status += "✅ OpenAI API 正常"
    except Exception as e:
        status += f"❌ OpenAI API 錯誤: {e}"
    await interaction.response.send_message(status)

# -------------------------
# 永遠運行保護
# -------------------------
async def keep_alive():
    while True:
        await asyncio.sleep(60)
        logging.info("💓 Bot 保活中...")

# -------------------------
# 主程序
# -------------------------
async def main():
    async with bot:
        bot.loop.create_task(keep_alive())
        await bot.start(DISCORD_TOKEN)

asyncio.run(main())
