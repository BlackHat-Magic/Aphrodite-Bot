# from discord.ext import commands, ipc
# from discord import app_commands
from datetime import datetime
from dotenv import load_dotenv
from discord.ext import commands
from PIL import Image, PngImagePlugin
from discord.ui import Button, Select, select
from concurrent.futures import ThreadPoolExecutor
from discord import app_commands, ButtonStyle, SelectOption
from controlnet_aux.processor import Processor
import discord, os, openai, tiktoken, re, requests, base64, io, runpod, time, asyncio, cv2, numpy

# set up environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
runpod.api_key = os.getenv("RUNPOD_API_KEY")
generic = runpod.Endpoint(os.getenv("RUNPOD_GENERIC_ENDPOINT"))
upscale = runpod.Endpoint(os.getenv("RUNPOD_UPSCALE_ENDPOINT"))
controlnet = runpod.Endpoint(os.getenv("RUNPOD_CONTROLNET_ENDPOINT"))

# set up system prompt
system_prompt = ""
with open("system_prompt_main.txt", "r") as file:
    system_prompt += file.read()
    system_prompt = system_prompt.replace("{{DATE}}", datetime.now().strftime("%Y-%m-%d"))

# set up thread namer
thread_namer = ""
with open("system_prompt_name_thread.txt", "r") as file:
    thread_namer += file.read()

intents = discord.Intents.default()
intents.message_content = True

# client = discord.Client(intents=intents)
client = commands.Bot(command_prefix="h!", intents=intents)

# instantiate the controlnet preprocessors
depthPreprocessor = Processor("depth_midas")
openposePreprocessor = Processor("openpose")
openposeFacePreprocessor = Processor("openpose_face")
openposeHandPreprocessor = Processor("openpose_hand")
openposeFullPreprocessor = Processor("openpose_full")

class PreprocessorDropdown(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60 )
        self.chosen_controlnet = None
    @select(placeholder="Select a preprocessor; Image will be cropped to a square and resized to 512x512 before preprocessing...", options=[
            # SelectOption(label="Blur", value="Blur"),
            SelectOption(label="Canny Edge", value="Canny Edge"),
            SelectOption(label="Depth Map", value="Depth"),
            SelectOption(label="Openpose", value="Openpose"),
            SelectOption(label="Openpose (with Face)", value="Openpose Face"),
            SelectOption(label="Openpose (with Hands)", value="Openpose Hand"),
            SelectOption(label="Openpose (Full)", value="Openpose Full")
    ])
    async def callback(self, interaction: discord.Interaction, select: Select):
        self.chosen_controlnet = select.values[0]
        self.stop()

class ControlNetDropdown(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.chosen_controlnet = None
    @select(placeholder="Select a controlnet model...", options = [
        SelectOption(label="Canny Edge", value="Canny Edge"),
        SelectOption(label="Depth Map", value="Depth Map"),
        SelectOption(label="Openpose (Any)", value="Openpose")
    ])
    async def callback(self, interaction: discord.Interaction, select: Select):
        self.chosen_controlnet = select.values[0]
        self.stop()

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
async def imagine(interaction: discord.Interaction, prompt: str, negative_prompt: str = None, aspect_ratio: str = None, repeat: int=1):
    if(repeat > 8):
        await interaction.response.send_message(
            "Too many repeats requested; aborting...",
            ephemeral=True
        )
        return
    if(repeat < 1):
        await interaction.response.send_message(
            "Invalid repeat number specified; aborting...",
            ephemeral=True
        )
        return
    userid = interaction.user.id
    repetitions = []

    for i in range(repeat):
        # deal with message
        embed = discord.Embed(
            title="Image Job",
            color=discord.Color.from_rgb(0, 255, 255)
        )
        embed.add_field(
            name="Status",
            value="In queue...",
            inline=True
        )
        embed.add_field(
            name="Prompt",
            value=prompt,
            inline=False
        )
        if(negative_prompt == None):
            displayed_negative_prompt = "Default (\"bad quality, worst quality, blurry, out of focus, cropped, out of frame, deformed, bad hands, bad anatomy\")"
        else:
            displayed_negative_prompt = negative_prompt
        embed.add_field(
            name="Negative Prompt",
            value=displayed_negative_prompt,
            inline=False
        )
        embed.add_field(
            name="Desired Aspect Ratio",
            value=aspect_ratio,
            inline=True
        )
        if(i == 0):
            await interaction.response.send_message(
                f"<@{userid}> Request processing...",
                embed=embed
            )
        else:
            await interaction.followup.send(
                f"<@{userid}> Request processing...",
                embed=embed
            )
        initial_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)

        # get aspect ratio
        desired_ratio = 1.0
        if(aspect_ratio and not re.match(r"^\d+:\d+$", aspect_ratio)):
            await initial_message.edit(
                contents="Invalid aspect ratio. Format as `width:height` (e.g. 16:9, 1:1). Numbers must be integers.",
                embeds=None
            )
            return
        if(aspect_ratio != None):
            desired_ratio = int(aspect_ratio.split(":")[0]) / int(aspect_ratio.split(":")[1])
        supported_ratios = [
            [0.42857, "9:21",  (640, 1536)], 
            [0.50000, "1:2",   (704, 1472)], 
            [0.56250, "9:16",  (768, 1344)], 
            [0.66667, "2:3",   (832, 1280)], 
            [0.68421, "13:19", (832, 1216)], 
            [0.72727, "8:11",  (896, 1216)], 
            [0.75000, "3:4",   (896, 1152)],
            [0.77778, "7:9",   (896, 1152)], 
            [1.00000, "1:1",   (1024, 1024)], 
            [1.28571, "9:7",   (1152, 896)], 
            [1.33333, "4:3",   (1152, 896)],
            [1.37500, "11:8",  (1216, 896)],
            [1.46154, "19:13", (1216, 832)],
            [1.50000, "3:2",   (1280, 832)],
            [1.77778, "16:9",  (1344, 768)],
            [2.00000, "2:1",   (1472, 704)],
            [2.33333, "21:9",  (1536, 640)]
        ]
        res_info = min(supported_ratios, key=lambda x:abs(x[0] - desired_ratio))
        width, height = res_info[2]
        embed.add_field(
            name="Quantized Aspect Ratio",
            value=res_info[1],
            inline=True
        )
        embed.add_field(
            name="Resolution",
            value=f"{width}x{height}",
            inline=True
        )
        await initial_message.edit(embed=embed)

        # set up post request
        if(negative_prompt == None):
            payload = {
                "prompt": prompt,
                "batch_size": 4,
                "width": width,
                "height": height
            }
        else:
            payload = {
                "prompt": prompt,
                "batch_size": 4,
                "width": width,
                "height": height,
                "negative_prompt": negative_prompt
            }
        
        # initialize serverless request
        run_request = generic.run(payload)

        repetitions.append({
            "message": initial_message,
            "runpod_request": run_request,
            "progress_started": False,
            "embed": embed,
            "uploaded": False
        })

    async def awaitResponse(repetition):
        while(True):
            initial_message = repetition["message"]
            status = repetition["runpod_request"].status()
            embed = repetition["embed"]
            if(status == "IN_PROGRESS" and not repetition["progress_started"]):
                embed.set_field_at(0, name="Status", value="In progress...")
                repetition["progress_started"] = True
                await initial_message.edit(embed=embed)
            if(status == "COMPLETED" and not repetition["uploaded"]):
                embed.set_field_at(0, name="Status", value="Loading images...")
                await initial_message.edit(embed=embed)

                output = repetition["runpod_request"].output()
                grid = Image.new("RGB", (width * 2, height * 2))
                grid.paste(Image.open(io.BytesIO(base64.b64decode(output[0]))), (0, 0))
                grid.paste(Image.open(io.BytesIO(base64.b64decode(output[1]))), (width, 0))
                grid.paste(Image.open(io.BytesIO(base64.b64decode(output[2]))), (0, height))
                grid.paste(Image.open(io.BytesIO(base64.b64decode(output[3]))), (width, height))

                sent_file = None
                with io.BytesIO() as image_binary:
                    grid.save(image_binary, "PNG")
                    image_binary.seek(0)
                    sent_file = discord.File(fp=image_binary, filename="grid.png")

                await initial_message.add_files(sent_file)
                embed.set_field_at(0, name="Status", value="Completed")
                view = discord.ui.View()
                view.add_item(Button(style=ButtonStyle.primary, label="U1", custom_id="upscale_1"))
                view.add_item(Button(style=ButtonStyle.primary, label="U2", custom_id="upscale_2"))
                view.add_item(Button(style=ButtonStyle.primary, label="U3", custom_id="upscale_3"))
                view.add_item(Button(style=ButtonStyle.primary, label="U4", custom_id="upscale_4"))
                await initial_message.edit(
                    content=f"<@{userid}> Request completed.",
                    embed=embed,
                    view=view
                )
                repetition["uploaded"] = True
                break
            await asyncio.sleep(1)
    
    await asyncio.gather(*(awaitResponse(repetition) for repetition in repetitions))

@client.tree.command(name="controlnet")
async def retrieve_controlnet(interaction: discord.Interaction, prompt: str, image_url: str, negative_prompt: str = None, aspect_ratio: str = None, repeat: int=1):
    if(repeat > 8):
        await interaction.response.send_message(
            "Too many repeats requested; aborting...",
            ephemeral=True
        )
        return
    if(repeat < 1):
        await interaction.response.send_message(
            "Invalid repeat number specified; aborting...",
            ephemeral=True
        )
        return
    userid = interaction.user.id
    repetitions = []
    
    view = ControlNetDropdown()
    await interaction.response.send_message("Select ControlNet model:", view=view)
    initial_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)

    try:
        response = requests.get(image_url)
        if(response.status_code != 200):
            view.clear_items()
            await initial_message.edit(content=f"Invalid image url. Returned code {response.status_code}", view=view, delete_after=30)
            return
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
    except Exception as e:
        view.clear_items()
        await initial_message.edit(content=f"Image failed to load. ({e})", view=view, delete_after=30)
        return

    await view.wait()
    view.clear_items()

    if(view.is_finished):
        if(view.chosen_controlnet == None):
            view.clear_items()
            await initial_message.edit(content="Interaction expired.", view=view, delete_after=30)
            return

    await initial_message.edit(content="Preprocessor model selected.", view=view)

    for i in range(repeat):
        # deal with message
        embed = discord.Embed(
            title="Image Job",
            color=discord.Color.from_rgb(0, 255, 255)
        )
        embed.add_field(
            name="Status",
            value="In queue...",
            inline=True
        )
        embed.add_field(
            name="Prompt",
            value=prompt,
            inline=False
        )
        if(negative_prompt == None):
            displayed_negative_prompt = "Default (\"bad quality, worst quality, blurry, out of focus, cropped, out of frame, deformed, bad hands, bad anatomy\")"
        else:
            displayed_negative_prompt = negative_prompt
        embed.add_field(
            name="Negative Prompt",
            value=displayed_negative_prompt,
            inline=False
        )
        embed.add_field(
            name="Desired Aspect Ratio",
            value=aspect_ratio,
            inline=True
        )
        await interaction.followup.send(
            f"<@{userid}> Request processing...",
            embed=embed
        )
        initial_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)

        # get aspect ratio
        desired_ratio = 1.0
        if(aspect_ratio and not re.match(r"^\d+:\d+$", aspect_ratio)):
            await initial_message.edit(
                contents="Invalid aspect ratio. Format as `width:height` (e.g. 16:9, 1:1). Numbers must be integers.",
                embeds=None
            )
            return
        if(aspect_ratio != None):
            desired_ratio = int(aspect_ratio.split(":")[0]) / int(aspect_ratio.split(":")[1])
        supported_ratios = [
            [0.42857, "9:21",  (640, 1536)], 
            [0.50000, "1:2",   (704, 1472)], 
            [0.56250, "9:16",  (768, 1344)], 
            [0.66667, "2:3",   (832, 1280)], 
            [0.68421, "13:19", (832, 1216)], 
            [0.72727, "8:11",  (896, 1216)], 
            [0.75000, "3:4",   (896, 1152)],
            [0.77778, "7:9",   (896, 1152)], 
            [1.00000, "1:1",   (1024, 1024)], 
            [1.28571, "9:7",   (1152, 896)], 
            [1.33333, "4:3",   (1152, 896)],
            [1.37500, "11:8",  (1216, 896)],
            [1.46154, "19:13", (1216, 832)],
            [1.50000, "3:2",   (1280, 832)],
            [1.77778, "16:9",  (1344, 768)],
            [2.00000, "2:1",   (1472, 704)],
            [2.33333, "21:9",  (1536, 640)]
        ]
        res_info = min(supported_ratios, key=lambda x:abs(x[0] - desired_ratio))
        width, height = res_info[2]
        embed.add_field(
            name="Quantized Aspect Ratio",
            value=res_info[1],
            inline=True
        )
        embed.add_field(
            name="Resolution",
            value=f"{width}x{height}",
            inline=True
        )
        await initial_message.edit(embed=embed)

        with io.BytesIO() as image_binary:
            image.save(image_binary, "PNG")
            sent_file = base64.b64encode(image_binary.getvalue()).decode("utf-8")
        
        if(view.chosen_controlnet == "Canny Edge"):
            model = "canny"
        elif(view.chosen_controlnet == "Depth Map"):
            model = "depth"
        else:
            model = "openpose"

        # set up post request
        if(negative_prompt == None):
            payload = {
                "prompt": prompt,
                "batch_size": 4,
                "width": width,
                "height": height,
                "images": [sent_file],
                "model": model
            }
        else:
            payload = {
                "prompt": prompt,
                "batch_size": 4,
                "width": width,
                "height": height,
                "negative_prompt": negative_prompt,
                "images": [sent_file],
                "model": model
            }
        
        # initialize serverless request
        run_request = controlnet.run(payload)

        repetitions.append({
            "message": initial_message,
            "runpod_request": run_request,
            "progress_started": False,
            "embed": embed,
            "uploaded": False
        })

    async def awaitResponse(repetition):
        while(True):
            initial_message = repetition["message"]
            status = repetition["runpod_request"].status()
            embed = repetition["embed"]
            if(status == "IN_PROGRESS" and not repetition["progress_started"]):
                embed.set_field_at(0, name="Status", value="In progress...")
                repetition["progress_started"] = True
                await initial_message.edit(embed=embed)
            if(status == "COMPLETED" and not repetition["uploaded"]):
                embed.set_field_at(0, name="Status", value="Loading images...")
                await initial_message.edit(embed=embed)

                output = repetition["runpod_request"].output()
                grid = Image.new("RGB", (width * 2, height * 2))
                grid.paste(Image.open(io.BytesIO(base64.b64decode(output[0]))), (0, 0))
                grid.paste(Image.open(io.BytesIO(base64.b64decode(output[1]))), (width, 0))
                grid.paste(Image.open(io.BytesIO(base64.b64decode(output[2]))), (0, height))
                grid.paste(Image.open(io.BytesIO(base64.b64decode(output[3]))), (width, height))

                sent_file = None
                with io.BytesIO() as image_binary:
                    grid.save(image_binary, "PNG")
                    image_binary.seek(0)
                    sent_file = discord.File(fp=image_binary, filename="grid.png")

                await initial_message.add_files(sent_file)
                embed.set_field_at(0, name="Status", value="Completed")
                view = discord.ui.View()
                view.add_item(Button(style=ButtonStyle.primary, label="U1", custom_id="upscale_1"))
                view.add_item(Button(style=ButtonStyle.primary, label="U2", custom_id="upscale_2"))
                view.add_item(Button(style=ButtonStyle.primary, label="U3", custom_id="upscale_3"))
                view.add_item(Button(style=ButtonStyle.primary, label="U4", custom_id="upscale_4"))
                await initial_message.edit(
                    content=f"<@{userid}> Request completed.",
                    embed=embed,
                    view=view
                )
                repetition["uploaded"] = True
                break
            await asyncio.sleep(1)
    
    await asyncio.gather(*(awaitResponse(repetition) for repetition in repetitions))

@client.tree.command(name="preprocess")
async def preprocessCommand(interaction: discord.Interaction, image_url: str):
    view = PreprocessorDropdown()
    await interaction.response.send_message("Select preprocessor model:", view=view)
    initial_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)

    try:
        response = requests.get(image_url)
        if(response.status_code != 200):
            view.clear_items()
            await initial_message.edit(content=f"Invalid URL. Returned code {response.status_code}.", delete_after=30, view=view)
            return
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
    except Exception as e:
        view.clear_items()
        await initial_message.edit(f"Image failed to load ({e}).", view=view, delete_after=30)
        return

    await view.wait()
    view.clear_items()

    if(view.is_finished):
        if(view.chosen_controlnet == None):
            view.clear_items()
            await initial_message.edit("Interaction expired.", view=view, delete_after=30)
            return

    await initial_message.edit(content="Preprocessor model selected.", view=view)

    # calculate crop
    width, height = image.size
    crop_size = min(width, height)
    left = int((height - crop_size) / 2)
    top = int((height - crop_size) / 2)
    right = int((width + crop_size) / 2)
    bottom = int((height + crop_size) / 2)

    # crop
    image = image.crop((left, top, right, bottom))

    # resize image and convert to numpy
    image = image.resize((512,512))
    image = numpy.array(image)

    is_PIL = False
    match view.chosen_controlnet:
        case "Canny Edge":
            preprocessed = cv2.Canny(image, 100, 200)
        case "Openpose":
            preprocessed = openposePreprocessor(image, to_pil=True)
            is_PIL = True
        case "Openpose Hand":
            preprocessed = openposeHandPreprocessor(image, to_pil=True)
            is_PIL = True
        case "Openpose Face":
            preprocessed = openposeFacePreprocessor(image, to_pil=True)
            is_PIL = True
        case "Openpose Full":
            preprocessed = openposeFullPreprocessor(image, to_pil=True)
            is_PIL = True
        case "Depth":
            preprocessed = depthPreprocessor(image, to_pil=True)
    
    with io.BytesIO() as image_binary:
        if(not bool(is_PIL)):
            preprocessed = Image.fromarray(preprocessed)
        preprocessed.save(image_binary, "PNG")
        image_binary.seek(0)
        sent_file = discord.File(fp=image_binary, filename="preprocessed.png")
    
    await interaction.followup.send("Image processed.")
    initial_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)
    await initial_message.add_files(sent_file)

@client.event
async def on_interaction(interaction):
    if(interaction.type == discord.InteractionType.component):
        # get interaction info
        custom_id = interaction.data["custom_id"]
        message = interaction.message
        userid = interaction.user.id

        # if it's an upscale interaction, upscale
        if(re.match(f"^upscale_\d$", custom_id)):
            # initial response
            fields = message.embeds[0].fields
            prompt = ""
            for field in fields:
                if(field.name == "Prompt"):
                    prompt = field.value
                    break
            embed = discord.Embed(
                title="Upscale Job",
                color=discord.Color.from_rgb(128, 0, 255)
            )
            embed.add_field(
                name="Status",
                value="In queue...",
                inline=True
            )
            embed.add_field(
                name="Prompt",
                value=prompt,
                inline=False
            )
            await interaction.response.send_message(
                f"<@{userid}> Upscaling image...",
                embed=embed
            )
            initial_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)

            # grab image
            image = Image.open(io.BytesIO(requests.get(message.attachments[0].url).content))

            # ypdate embed
            embed.add_field(
                name="Original Resolution",
                value=f"{int(image.width / 2)}x{int(image.height / 2)}",
                inline=True
            )
            embed.add_field(
                name="New Resolution",
                value=f"{image.width}x{image.height}",
                inline=True
            )
            await initial_message.edit(embed=embed)

            # crop image
            top, left, right, bottom = 0, 0, int(image.width / 2), int(image.height / 2)
            if(custom_id == "upscale_2"):
                left, right = int(image.width / 2), image.width
            if(custom_id == "upscale_3"):
                top, bottom = int(image.height / 2), image.height
            if(custom_id == "upscale_4"):
                top, left, right, bottom = int(image.height / 2), int(image.width / 2), image.width, image.height
            cropped_image = image.crop((left, top, right, bottom))

            # encode b64
            with io.BytesIO() as image_binary:
                cropped_image.save(image_binary, "PNG")
                sent_file = base64.b64encode(image_binary.getvalue()).decode("utf-8")
            payload = {
                "prompt": prompt,
                "image": sent_file
            }

            # send runpod request
            run_request = upscale.run(payload)
            progress_started = False
            while(True):
                status = run_request.status()
                if(status == "IN_PROGRESS" and not progress_started):
                    embed.set_field_at(0, name="Status", value="In progress...")
                    progress_started = True
                    await initial_message.edit(embed=embed)
                if(status == "COMPLETED"):
                    embed.set_field_at(0, name="Status", value="Loading images...")
                    await initial_message.edit(embed=embed)
                    break
                await asyncio.sleep(1)

            # receive output
            output = Image.open(io.BytesIO(base64.b64decode(run_request.output()[0])))

            sent_file = None
            with io.BytesIO() as image_binary:
                output.save(image_binary, "PNG")
                image_binary.seek(0)
                sent_file = discord.File(fp=image_binary, filename="grid.png")

            await initial_message.add_files(sent_file)
            embed.set_field_at(0, name="Status", value="Completed")
            await initial_message.edit(
                content="Request completed.",
                embed=embed
            )
client.run(os.getenv("DISCORD_CLIENT_TOKEN"))
