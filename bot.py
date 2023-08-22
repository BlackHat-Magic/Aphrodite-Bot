# from discord.ext import commands, ipc
# from discord import app_commands
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from PIL import Image, PngImagePlugin
import discord, os, openai, tiktoken, re, random, requests, json, base64, io, runpod, time, asyncio

# set up environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
runpod.api_key = os.getenv("RUNPOD_API_KEY")
generic = runpod.Endpoint(os.getenv("RUNPOD_GENERIC_ENDPOINT"))
portrait = runpod.Endpoint(os.getenv("RUNPOD_PORTRAIT_ENDPOINT"))
charsheet = runpod.Endpoint(os.getenv("RUNPOD_CHARSHEET_ENDPOINT"))

# set up system prompt
system_prompt = ""
with open("system_prompt_main.txt", "r") as file:
    system_prompt += file.read()

# set up thread namer
thread_namer = ""
with open("system_prompt_name_thread.txt", "r") as file:
    thread_namer += file.read()

googler = ""
with open("system_prompt_google.txt", "r") as file:
    googler += file.read()

intents = discord.Intents.default()
intents.message_content = True

# client = discord.Client(intents=intents)
client = commands.Bot(command_prefix="h!", intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}.")
    try:
        synced = await client.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

@client.event
async def on_message(message):
    if(message.author == client.user):
        return
    if(isinstance(message.channel, discord.DMChannel)):
        # get list of messages
        messages = reversed([message async for message in message.channel.history(limit=100)])
        print("Obtained channel history")

        # set up empty conversation
        gpt_convo = [{
            "role": "system",
            "content": system_prompt
        }]

        # add messages to conversation
        for message in messages:
            role = "user"
            if(message.author == client.user):
                role = "assistant"
            content = message.content
            user_ids = re.findall("<@(\d+)>", content)
            for user_id in user_ids:
                user = await client.fetch_user(user_id)
                username = f"{user.name}#{user.discriminator}"
                if(user == client.user):
                    username = "Zoey"
                elif(user.discriminator == "0"):
                    username = user.name
                content = content.replace(f"<@{user_id}>", user.name)
            gpt_convo.append({
                "role": role,
                "content": content
            })
        print("Assembled Conversation")

        # reduce conversation size until it fits within 4096 token limit with space for response.
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        while len(encoding.encode("".join([f"{message['role']} {message['content']}\n" for message in gpt_convo]))) > 15360:
            gpt_convo.pop(1)
        print(f"Truncated Conversation to {len(gpt_convo)} messages")

        if(len(encoding.encode("".join([f"{message['role']} {message['content']}\n" for message in gpt_convo]))) > 3072):
            model = "gpt-3.5-turbo-16k"
        else:
            model = "gpt-3.5-turbo"
        
        # Obtain ClosedAI response
        print("Obtaining ClosedAI response...")
        response = openai.ChatCompletion.create(
            model=model,
            messages=gpt_convo
        )

        # reduce size until fits within context length
        await message.channel.send(response["choices"][0]["message"]["content"])
        return
    if(client.user in message.mentions):
        if(not "Zoey" in message.channel.name):
            # parse message content
            content = message.content
            user_ids = re.findall("<@(\d+)>", content)
            for user_id in user_ids:
                user = await client.fetch_user(user_id)
                username = f"{user.name}#{user.discriminator}"
                if(user == client.user):
                    username = "Zoey"
                elif(user.discriminator == "0"):
                    username = user.name
                content = content.replace(f"<@{user_id}>", user.name)
            print("Parsed message content.")
            
            # set up conversation
            gpt_convo = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": content
                }
            ]

            # get ClosedAI response
            closedai_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=gpt_convo
            )
            response = closedai_response["choices"][0]["message"]["content"]
            print("Obtained response.")

            # set up thread naming conversation
            thread_convo = [
                {
                    "role": "system",
                    "content": thread_namer
                },
                {
                    "role": "user",
                    "content": content
                },
                {
                    "role": "assistant",
                    "content": response
                }
            ]
            thread_name_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=thread_convo
            )
            thread_name = thread_name_response["choices"][0]["message"]["content"]
            print("Named Thread")

            # create thread and send message
            thread = await message.create_thread(name=f"Zoey: {thread_name}", auto_archive_duration=60, slowmode_delay=None, reason=None)
            await thread.send(response)
            return
        else:
            # get list of messages
            messages = reversed([message async for message in message.channel.history(limit=100)])
            print("Obtained channel history")

            # set up empty conversation
            gpt_convo = [{
                "role": "system",
                "content": system_prompt
            }]

            # add messages to conversation
            for message in messages:
                role = "user"
                if(message.author == client.user):
                    role = "assistant"
                content = message.content
                user_ids = re.findall("<@(\d+)>", content)
                for user_id in user_ids:
                    user = await client.fetch_user(user_id)
                    username = f"{user.name}#{user.discriminator}"
                    if(user == client.user):
                        username = "Zoey"
                    elif(user.discriminator == "0"):
                        username = user.name
                    content = content.replace(f"<@{user_id}>", user.name)
                gpt_convo.append({
                    "role": role,
                    "content": content
                })
            print("Assembled Conversation")

            # reduce conversation size until it fits within 4096 token limit with space for response.
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            while len(encoding.encode("".join([f"{message['role']} {message['content']}\n" for message in gpt_convo]))) > 15360:
                gpt_convo.pop(1)
            print(f"Truncated Conversation to {len(gpt_convo)} messages")

            if(len(encoding.encode("".join([f"{message['role']} {message['content']}\n" for message in gpt_convo]))) > 3072):
                model = "gpt-3.5-turbo-16k"
            else:
                model = "gpt-3.5-turbo"
            
            # Obtain ClosedAI response
            print("Obtaining ClosedAI response...")
            response = openai.ChatCompletion.create(
                model=model,
                messages=gpt_convo
            )
            # reduce size until fits within context length
            await message.reply(response["choices"][0]["message"]["content"])
            return

@client.tree.command(name="imagine")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    userid = interaction.user.id
    # set up post request
    payload = {
        "prompt": prompt,
        "batch_size": 4,
    }

    # get API response
    run_request = generic.run(payload)
    while(True):
        status = run_request.status()
        print(status.casefold().capitalize().replace("_", " "))
        if(status == "COMPLETED"):
            print("Image Completed")
            break
        await asyncio.sleep(1)

    # save images
    files = []
    output = run_request.output()
    for i, image in enumerate(output):
        #open the image
        png = Image.open(io.BytesIO(base64.b64decode(image)))

        # save the image
        png.save(f"{userid}-output-{i}.png")

        with open(f"{userid}-output-{i}.png", "rb") as f:
            files.append(discord.File(f, filename=f"output-{i}.png"))
    

    # button1 = discord.ui.Button(style=discord.ButtonStyle.primary, label="Upscale 1")
    # button2 = discord.ui.Button(style=discord.ButtonStyle.primary, label="Upscale 2")
    # button3 = discord.ui.Button(style=discord.ButtonStyle.primary, label="Upscale 3")
    # button4 = discord.ui.Button(style=discord.ButtonStyle.primary, label="Upscale 4")

    # view = discord.ui.View()
    # view.add_item(button1)
    # view.add_item(button2)
    # view.add_item(button3)
    # view.add_item(button4)

    await interaction.followup.send(files=files)

@client.tree.command(name="portrait")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    userid = interaction.user.id
    # set up post request
    payload = {
        "prompt": prompt,
        "batch_size": 4,
    }

    # get API response
    run_request = portrait.run(payload)
    while(True):
        status = run_request.status()
        if(status == "COMPLETED"):
            break
        time.sleep(1)

    # save images
    files = []
    output = run_request.output()
    for i, image in enumerate(output):
        #open the image
        png = Image.open(io.BytesIO(base64.b64decode(image)))

        # save the image
        png.save(f"{userid}-output-{i}.png")

        with open(f"{userid}-output-{i}.png", "rb") as f:
            files.append(discord.File(f, filename=f"output-{i}.png"))

    await interaction.followup.send(files=files)

# someday
# @client.tree.command(name="roll")
# async def roll(interaction: discord.Interaction, dice: str):

client.run(os.getenv("DISCORD_CLIENT_TOKEN"))