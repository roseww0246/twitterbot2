import os
import discord
from discord import app_commands
from discord.ext import commands
from fastapi import FastAPI
import uvicorn
import asyncio
import openai
import logging
import aiohttp
from io import BytesIO

# ----------------- 設定 -----------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", 8080))

if not DISCORD_TOKEN or not OPENAI_API_KEY:
    raise ValueError("請確認環境變數 DISCORD_TOKEN 與 OPENAI_API_KEY 已設定")

openai.api_key = OPENAI_API_KEY

intents = discord.Intents.default()
intents.message_content = True

logging.basicConfig(level=logging.INFO)

# ----------------- Discord Bot -----------------
class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

client = MyClient(intents=intents)

@client.event
async def on_ready():
    await client.tree.sync()
    logging
