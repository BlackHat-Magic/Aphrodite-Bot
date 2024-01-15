# from discord.ext import commands, ipc
# from discord import app_commands
from datetime import datetime
from dotenv import load_dotenv
from discord.ext import commands
from PIL import Image, PngImagePlugin
from discord.ui import Button, Select, select, button
from discord import ButtonStyle, SelectOption
from controlnet_aux.processor import Processor
import discord, os, re, requests, base64, io, runpod, time, asyncio, cv2, numpy

# set up environment variables
load_dotenv()
runpod.api_key = os.getenv("RUNPOD_API_KEY")
generic = runpod.Endpoint(os.getenv("RUNPOD_GENERIC_ENDPOINT"))
upscale = runpod.Endpoint(os.getenv("RUNPOD_UPSCALE_ENDPOINT"))
controlnet = runpod.Endpoint(os.getenv("RUNPOD_CONTROLNET_ENDPOINT"))

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="h!", intents=intents)

# instantiate the controlnet preprocessors
depthPreprocessor = Processor("depth_midas")
openposePreprocessor = Processor("openpose")
openposeFacePreprocessor = Processor("openpose_face")
openposeHandPreprocessor = Processor("openpose_hand")
openposeFullPreprocessor = Processor("openpose_full")

class ImageEmbed(discord.Embed):
    def __init__(self, title, rgb, prompt, negative_prompt, aspect_ratio, quantized_aspect_ratio, resolution):
        super().__init__(title=title, color=discord.Color.from_rgb(*(rgb)))
        self.add_field(name="Status", value="In queue...", inline=True)
        self.add_field(name="Prompt", value=prompt, inline=False)
        self.add_field(name="Negative Prompt", value=negative_prompt, inline=False)
        self.add_field(name="Desired Aspect Ratio", value=aspect_ratio, inline=True)
        self.add_field(name="Quantized Aspect Ratio", value=quantized_aspect_ratio, inline=True)
        self.add_field(name="Resolution", value="{}x{}".format(*resolution), inline=True)

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
            SelectOption(label="Openpose (Hands Only)", value="Openpose Hand"),
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

class ImageButtons(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.upscaled_urls = [None, None, None, None]
        self.add_item(Button(style=ButtonStyle.primary, label="U1", custom_id="upscale_0", row=0, emoji="↕"))
        self.add_item(Button(style=ButtonStyle.primary, label="U2", custom_id="upscale_1", row=0, emoji="↕"))
        self.add_item(Button(style=ButtonStyle.primary, label="U3", custom_id="upscale_2", row=1, emoji="↕"))
        self.add_item(Button(style=ButtonStyle.primary, label="U4", custom_id="upscale_3", row=1, emoji="↕"))

async def awaitResponse(repetition, userid):
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
            images = [Image.open(io.BytesIO(base64.b64decode(image))) for image in output]
            width, height = images[0].size
            if(len(images) == 1):
                grid = Image.new("RGB", (width, height))
                grid.paste(images[0], (0, 0))
            else:
                grid = Image.new("RGB", (width * 2, height * 2))
                grid.paste(images[0], (0, 0))
                grid.paste(images[1], (width, 0))
                grid.paste(images[2], (0, height))
                grid.paste(images[3], (width, height))

            with io.BytesIO() as image_binary:
                grid.save(image_binary, "PNG")
                image_binary.seek(0)
                sent_file = discord.File(fp=image_binary, filename="grid.png")

            await initial_message.add_files(sent_file)
            embed.set_field_at(0, name="Status", value="Completed")
            view = ImageButtons()
            await initial_message.edit(
                content=f"<@{userid}> Request completed.",
                embed=embed,
                view=view
            )
            repetition["uploaded"] = True
            break
        await asyncio.sleep(1)

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

@client.event
async def on_ready():
    print(f"Logged in as {client.user}.")
    try:
        synced = await client.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

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
        # parse negative_prompt
        if(negative_prompt == None):
            displayed_negative_prompt = "Default (\"bad quality, worst quality, blurry, out of focus, cropped, out of frame, deformed, bad hands, bad anatomy\")"
        else:
            displayed_negative_prompt = negative_prompt

        # get aspect ratio
        desired_ratio = 1.0
        if(aspect_ratio and not re.match(r"^\d+:\d+$", aspect_ratio)):
            await interaction.response.send_message(
                contents="Invalid aspect ratio. Format as `width:height` (e.g. 16:9, 1:1). Numbers must be integers.",
                embeds=None,
                ephemeral=True
            )
            return
        if(aspect_ratio != None):
            desired_ratio = int(aspect_ratio.split(":")[0]) / int(aspect_ratio.split(":")[1])
        res_info = min(supported_ratios, key=lambda x:abs(x[0] - desired_ratio))
        width, height = res_info[2]

        # setup embed
        embed = ImageEmbed("Image Job", (0, 255, 255), prompt, displayed_negative_prompt, aspect_ratio, res_info[1], res_info[2])
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
        if(type(interaction.channel) == discord.DMChannel):
            async for message in interaction.channel.history(limit=1):
                initial_message = message
        else:
            initial_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)

        # set up post request
        if(negative_prompt == None):
            payload = {
                "prompt": prompt,
                "batch_size": 4,
                "width": width,
                "height": height,
            }
        else:
            payload = {
                "prompt": prompt,
                "batch_size": 4,
                "width": width,
                "height": height,
                "negative_prompt": negative_prompt,
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
    
    await asyncio.gather(*(awaitResponse(repetition, userid) for repetition in repetitions))

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
        # parse negative_prompt
        if(negative_prompt == None):
            displayed_negative_prompt = "Default (\"bad quality, worst quality, blurry, out of focus, cropped, out of frame, deformed, bad hands, bad anatomy\")"
        else:
            displayed_negative_prompt = negative_prompt

        # get aspect ratio
        desired_ratio = 1.0
        if(aspect_ratio and not re.match(r"^\d+:\d+$", aspect_ratio)):
            await interaction.response.send_message(
                contents="Invalid aspect ratio. Format as `width:height` (e.g. 16:9, 1:1). Numbers must be integers.",
                embeds=None,
                ephemeral=True
            )
            return
        if(aspect_ratio == None):
            desired_ratio = image.width / image.height
        else:
            desired_ratio = int(aspect_ratio.split(":")[0]) / int(aspect_ratio.split(":")[1])
        res_info = min(supported_ratios, key=lambda x:abs(x[0] - desired_ratio))
        width, height = res_info[2]

        # setup embed
        embed = ImageEmbed("Controlnet Job", (255, 128, 0), prompt, displayed_negative_prompt, aspect_ratio, res_info[1], res_info[2])
        await interaction.followup.send(
            f"<@{userid}> Request processing...",
            embed=embed
        )
        initial_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)

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
    
    await asyncio.gather(*(awaitResponse(repetition, userid) for repetition in repetitions))

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
            await initial_message.edit(content="Interaction expired.", view=view, delete_after=30)
            return

    await initial_message.edit(content="Preprocessor model selected. (loading...)", view=view)

    # paste
    width, height = image.size
    resize_ratio = 512 / min(width, height)
    image = image.resize((int(resize_ratio * width), int(resize_ratio * height)))
    arr_image = numpy.array(image)

    is_PIL = False
    loop = asyncio.get_event_loop()
    match view.chosen_controlnet:
        case "Canny Edge":
            preprocessed = await loop.run_in_executor(None, lambda: cv2.Canny(arr_image, 100, 200))
        case "Openpose":
            preprocessed = await loop.run_in_executor(None, lambda: openposePreprocessor(arr_image, to_pil=True))
            is_PIL = True
        case "Openpose Hand":
            preprocessed = await loop.run_in_executor(None, lambda: openposeHandPreprocessor(arr_image, to_pil=True))
            is_PIL = True
        case "Openpose Face":
            preprocessed = await loop.run_in_executor(None, lambda: openposeFacePreprocessor(arr_image, to_pil=True))
            is_PIL = True
        case "Openpose Full":
            preprocessed = await loop.run_in_executor(None, lambda: openposeFullPreprocessor(arr_image, to_pil=True))
            is_PIL = True
        case "Depth":
            preprocessed = await loop.run_in_executor(None, lambda: depthPreprocessor(arr_image, to_pil=True))
    
    await initial_message.edit(content="Preprocessor model selected.")
    
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
    if(interaction.type != discord.InteractionType.component):
        return
    custom_id = interaction.data["custom_id"]
    message = interaction.message
    userid = interaction.user.id
    if(re.match(f"^upscale_\d$", custom_id)):
        # get message data
        fields  = message.embeds[0].fields
        prompt = None
        for field in fields:
            if(field.name == "Prompt"):
                prompt = field.value
                break
        if(prompt == None):
            await interaction.response.send_message("Unable to load prompt from original message.", ephemeral=True)
            return
        negative_prompt = "bad quality, worst quality, blurry, out of focus, cropped, out of frame, deformed, bad hands, bad anatomy"
        for field in fields:
            if(field.name == "Negative Prompt"):
                negative_prompt = field.value
                break
        aspect_ratio = ""
        for field in fields:
            if(field.name == "Quantized Aspect Ratio"):
                aspect_ratio = field.value
                break

        # create embed
        embed = ImageEmbed("Upscale Job", (128, 0, 255), prompt, negative_prompt, aspect_ratio, aspect_ratio, (1024, 1024))

        # send initial message
        await interaction.response.send_message(
            f"<@{userid}> Upscaling image...",
            embed=embed
        )
        initial_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)

        # download original image
        try:
            response  = requests.get(message.attachments[0].url)
            response.raise_for_status()
        except:
            await interaction.followup.send("Failed to get image.", ephemeral=True)
            await initial_message.delete()
            return
        image_binary = response.content
        image = Image.open(io.BytesIO(image_binary))
        embed.set_field_at(
            3,
            name="Original Resolution",
            value=f"{image.width // 2}x{image.height // 2}",
            inline=True
        )
        embed.set_field_at(
            4,
            name="New Resolution",
            value=f"{image.width}x{image.height}",
            inline=True
        )
        embed.remove_field(5)
        await initial_message.edit(embed=embed)

        # crop image
        top, left, right, bottom = 0, 0, image.width // 2, image.height // 2
        if(custom_id == "upscale_2"):
            left, right = image.width // 2, image.width
        if(custom_id == "upscale_3"):
            top, bottom = image.height // 2, image.height
        if(custom_id == "upscale_4"):
            top, left, right, bottom = image.height // 2, image.width // 2, image.width, image.height
        cropped_image = image.crop((left, top, right, bottom))

        # send runpod request
        with io.BytesIO() as image_binary:
            cropped_image.save(image_binary, "PNG")
            image_binary.seek(0)
            sent_file = base64.b64encode(image_binary.getvalue()).decode("utf-8")
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "image": sent_file
        }
        run_request = upscale.run(payload)
        request_metadata = {
            "message": initial_message,
            "runpod_request": run_request,
            "progress_started": False,
            "embed": embed,
            "uploaded": False
        }
        await awaitResponse(request_metadata, userid)

client.run(os.getenv("DISCORD_CLIENT_TOKEN"))
