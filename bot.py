# from discord.ext import commands, ipc
# from discord import app_commands
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from PIL import Image, PngImagePlugin
import discord, os, openai, tiktoken, re, random, requests, json, base64

# set up environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

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

SD_URL = os.getenv("SD_URL")
try:
    requests.post(
        url=f"{SD_URL}/sdapi/v1/options",
        json = {
            "sd_model_checkpoint": "Baked-VAE-DreamShaper-v5.safetensors [a60cfaa90d]"
        }
    )
except:
    print("No A1111 UI detected; proceeding without")

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

@client.tree.command(name="coinflip")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(f"You flipped {random.choice(['heads','tails'])}!")

@client.tree.command(name="8ball")
async def eightball(interaction: discord.Interaction, message: str):
    options = [
        "It is certain",
        "It is decidedly so",
        "Without a doubt",
        "Yes definitiely",
        "You may rely on it",
        "As I see it, yes",
        "Most likely",
        "Outlook good",
        "Yes",
        "Signs point to yes",
        "reply hazy, try again",
        "Ask again later",
        "Better not tell you now",
        "Cannot predict now",
        "Concentrate and ask again",
        "Don't count on it",
        "My reply is no",
        "My sources say no",
        "Outlook not so good",
        "Very doubtful"
    ]
    await interaction.response.send_message(random.choice(options))

@client.tree.command(name="embed")
async def embed(interaction: discord.Interaction, text: str):
    args = text.split("|")
    title = args[0]
    description = args[1]
    color = discord.Color(int(args[2], 16))
    embed = discord.Embed(title=title, description=description, color=color)
    args = args[3:]
    for arg in args:
        parsed = arg.split(";")
        if(parsed[0] == "field"):
            embed.add_field(name=parsed[1], value=parsed[2])
            continue
        elif(parsed[0] == "inline-field"):
            embed.add_field(name=parsed[1], value=parsed[2])
        elif(parsed[0] == "footer"):
            embed.set_footer(text=parsed[1])
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="imagine")
async def imagine(interaction: discord.Interaction, prompt: str):
    userid = interaction.user.id
    # set up post request
    payload = {
        "prompt": f"good quality, best quality,\n\n{prompt}",
        "steps": 30,
        "negative_prompt": "blurry, out of focus, cropped, out of frame, bad quality, worst quality, bad hands, deformed, bad anatomy"
    }

    # get API response
    response = requests.post(url=f"{SD_URL}/sdapi/v1/txt2img", json=payload).json()
    print(f"RESPONSE: {response}")
    print(response.keys())

    # save images
    for i, image in enumerate(response['images']):
        #open the image
        png = Image.open(io.BytesIO(base64.b64decode(i.split(",",1)[0])))

        #get the image info
        png_payload = {
            "image": f"data:image/png;base64,{image}"
        }
        info = requests.post(url=f"{SD_URL}/sdapi/v1/png-info", json=png_payload).json().get("info")

        #add the image metadata to the file
        imginfo = PngImagePlugin.PngInfo()
        imginfo.add_text("parameters", info)

        # save the image
        image.save(f"{userid}-output-{i}.png", pnginfo=pnginfo)

        button1 = discord.ui.Button(style=discord.ButtonStyle.primary, label="Upscale 1")
        button2 = discord.ui.Button(style=discord.ButtonStyle.primary, label="Upscale 2")
        button3 = discord.ui.Button(style=discord.ButtonStyle.primary, label="Upscale 3")
        button4 = discord.ui.Button(style=discord.ButtonStyle.primary, label="Upscale 4")

        view = discord.ui.View()
        view.add_item(button1)
        view.add_item(button2)
        view.add_item(button3)
        view.add_item(button4)

        files = []
        for i in range(4):
            with open(f"{userid}-output-{i}.png") as f:
                files.append(discord.File(f, filename=f"output-{i}.png"))

        await interaction.response.send_message(view=view, files=files)

# someday
# @client.tree.command(name="roll")
# async def roll(interaction: discord.Interaction, dice: str):

# won't be big :(
# @client.tree.command(name="bigtext")
# async def bigtext(interaction: discord.Interaction, thing_to_say: str):
#     letter_dict = {
#         "a": ":regional_indicator_a:",
#         "b": ":regional_indicator_b:",
#         "c": ":regional_indicator_c:",
#         "d": ":regional_indicator_d:",
#         "e": ":regional_indicator_e:",
#         "f": ":regional_indicator_f:",
#         "g": ":regional_indicator_g:",
#         "h": ":regional_indicator_h:",
#         "i": ":regional_indicator_i:",
#         "j": ":regional_indicator_j:",
#         "k": ":regional_indicator_k:",
#         "l": ":regional_indicator_l:",
#         "m": ":regional_indicator_m:",
#         "n": ":regional_indicator_n:",
#         "o": ":regional_indicator_o:",
#         "p": ":regional_indicator_p:",
#         "q": ":regional_indicator_q:",
#         "r": ":regional_indicator_r:",
#         "s": ":regional_indicator_s:",
#         "t": ":regional_indicator_t:",
#         "u": ":regional_indicator_u:",
#         "v": ":regional_indicator_v:",
#         "w": ":regional_indicator_w:",
#         "x": ":regional_indicator_x:",
#         "y": ":regional_indicator_y:",
#         "z": ":regional_indicator_z:",
#         " ": "   ",
#         "1": ":one:",
#         "2": ":two:",
#         "3": ":three:",
#         "4": ":four:",
#         "5": ":five:",
#         "6": ":six:",
#         "7": ":seven:",
#         "8": ":eight:",
#         "9": ":nine:",
#         "0": ":zero:",
#         "!": ":exclamation:",
#         "?": ":question:"
#     }
#     output = ""
#     for letter in thing_to_say.casefold():
#         output += letter_dict.get(letter, "")
#     if(len(output) < 1):
#         output = "Output was empty."
#     await interaction.response.send_message(output)

client.run(os.getenv("DISCORD_CLIENT_TOKEN"))