# from discord.ext import commands, ipc
# from discord import app_commands
from discord.ext import commands
from image_cog import ImageCog
from datetime import datetime
from dotenv import load_dotenv
import discord, os, re, requests, base64, io, runpod, time, asyncio, cv2, numpy, json

load_dotenv()
DISCORD_CLIENT_TOKEN = os.getenv("DISCORD_CLIENT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="h!", intents=intents)

with open("./styles.json", "r") as file:
    style_dict = json.load(file)
styles = list(style_dict.keys())
if("Enhance" in styles):
    styles.remove("Enhance")

async def prepareBot():
    await client.add_cog(ImageCog(client))

@client.event
async def on_ready():
    print(f"Logged in as {client.user}.")
    try:
        await prepareBot()
        synced = await client.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

client.run(DISCORD_CLIENT_TOKEN)
