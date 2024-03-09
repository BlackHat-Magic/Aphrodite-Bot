from discord.ext import commands
from image_cog import ImageCog
from dotenv import load_dotenv
import discord, os, sys

load_dotenv()
DISCORD_CLIENT_TOKEN = os.getenv("DISCORD_CLIENT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="h!", intents=intents)

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
        sys.exit()

client.run(DISCORD_CLIENT_TOKEN)
