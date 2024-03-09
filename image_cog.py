from controlnet_aux.processor import Processor
from awaitResponse import awaitResponse
from discord import app_commands
from discord.ext import commands
from ui_utils import ImageEmbed
from dotenv import load_dotenv
from PIL import Image
import discord, runpod, asyncio, json, os, io, base64, cv2, numpy, re, requests

# set up environment variables
load_dotenv()
runpod.api_key = os.getenv("RUNPOD_API_KEY")
generic = runpod.Endpoint(os.getenv("RUNPOD_GENERIC_ENDPOINT"))
upscale = runpod.Endpoint(os.getenv("RUNPOD_UPSCALE_ENDPOINT"))
controlnet = runpod.Endpoint(os.getenv("RUNPOD_CONTROLNET_ENDPOINT"))

with open("./styles.json", "r") as f:
    style_dict = json.load(f)
styles = list(style_dict.keys())
if("Enhance" in styles):
    styles.remove("Enhance")

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


# instantiate the controlnet preprocessors
depthPreprocessor = Processor("depth_midas")
openposePreprocessor = Processor("openpose")
openposeFacePreprocessor = Processor("openpose_face")
openposeHandPreprocessor = Processor("openpose_hand")
openposeFullPreprocessor = Processor("openpose_full")
preprocessors = {
    "Canny Edge": depthPreprocessor,
    "Depth Map": openposePreprocessor,
    "Openpose (With Face)": openposeFacePreprocessor,
    "Openpose (Hands Only)": openposeHandPreprocessor,
    "Openpose (Full)": openposeFullPreprocessor
}

class ImageCog(commands.Cog):
    def __init__(self, client):
        self.client = client
    async def generate_image(
        self,
        interaction: discord.Interaction, 
        prompt: str, 
        style: str=None, 
        negative_prompt: str=None, 
        aspect_ratio: str=1.0, 
        repeat: int=1, 
        conditioning: dict=None
    ):
        # invalid stuff
        if(repeat > 8):
            interaction.followup.send(
                "Too many repeats requested; aborting...",
                ephemeral=True
            )
            return
        if(repeat < 1):
            interaction.followup.send(
                "Invalid repeat number specified; aborting...",
                ephemeral=True
            )
            return
        
        sent_file = None
        model = None
        if(conditioning):
            with io.BytesIO() as image_binary:
                conditioning["conditioning"].save(image_binary, "PNG")
                sent_file = base64.b64encode(image_binary.getvalue()).decode("utf-8")
            if("controlnet" in conditioning["name"]):
                model = conditioning["name"].split("_")[0]
        if(model):
            statsus = "Controlnet Job"
            color = (255, 128, 0)
        elif(sent_file):
            statsus = "Upscale Job"
            color = (128, 0, 255)
        else:
            statsus = "Image Job"
            color = (0, 255, 255)

        userid = interaction.user.id
        repetitions = []

        # positive prompt
        if(style == "Enhance" or style == None):
            template = style_dict["Enhance"]
        else:
            template = style_dict[style]
        true_prompt = template["positive"].format(prompt=prompt)

        # negative prompt
        if(negative_prompt and style != "Raw Prompt"):
            true_negative_prompt = f"{template['negative']}, {negative_prompt}"
        else:
            true_negative_prompt = negative_prompt
        
        # aspect ratio
        desired_ratio = 1.0
        res_info = min(supported_ratios, key=lambda x:abs(x[0] - desired_ratio))
        width, height = res_info[2]

        # repetitions
        for i in range(repeat):
            # send embed
            embed = ImageEmbed(
                "Image Job", 
                (0, 255, 255), 
                prompt, 
                style, 
                negative_prompt,
                aspect_ratio,
                res_info[1],
                res_info[2]
            )
            await interaction.followup.send(
                f"<@{userid}> Request processing...",
                embed=embed
            )
        
            # get the latest image
            if(type(interaction.channel) == discord.DMChannel):
                async for message in interaction.channel.history(limit=1):
                    initial_message = message
            else:
                initial_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)
            
            payload = {
                "prompt": true_prompt,
                "negative_prompt": true_negative_prompt,
                "num_images": 4,
                "width": width,
                "height": height,
                "images": [sent_file],
                "model": model
            }
            if(model):
                run_request = controlnet.run(payload)
            elif(sent_file):
                run_request = upscale.run(payload)
            else:
                run_request = generic.run(payload)
            repetitions.append({
                "message": initial_message,
                "runpod_request": run_request,
                "progress_started": False,
                "embed": embed,
                "uploaded": False
            })

        await asyncio.gather(*(awaitResponse(repetition, userid, "upscale") for repetition in repetitions))
    
    @app_commands.command(name="imagine")
    @app_commands.describe(style="Style your image")
    @app_commands.choices(
        style=[app_commands.Choice(name=style, value=style) for style in styles],
        aspect_ratio=[app_commands.Choice(name=ratio[1], value=ratio[1]) for ratio in supported_ratios]
    )
    async def imagine(
        self,
        interaction: discord.Interaction, 
        prompt: str, 
        style: str=None, 
        negative_prompt: str=None, 
        aspect_ratio: str=None, 
        repeat: int=1
    ):
        await interaction.response.defer()
        await self.generate_image(
            interaction, 
            prompt,
            style, 
            negative_prompt, 
            aspect_ratio, 
            repeat, 
            None
        )
    
    @app_commands.command(name="controlnet")
    @app_commands.describe(style="Style your image", image_url="The URL of the PREPROCESSED image to be used for conditioning. istg if you message me about controlnet looking wonky and I find out you're not preprocessing the images with the /preprocess command, I will personally remove your spine. rtfm.")
    @app_commands.choices(
        style=[app_commands.Choice(name=style, value=style) for style in styles],
        aspect_ratio=[app_commands.Choice(name=ratio[1], value=ratio[1]) for ratio in supported_ratios],
        preprocessor=[app_commands.Choice(name=preprocessor, value=preprocessor.split(" ")[0].casefold()) for preprocessor in preprocessors.keys()]
    )
    async def controlnet_command(
        self,
        interaction: discord.Interaction, 
        prompt: str, 
        image_url: str,
        preprocessor: str,
        style: str=None, 
        negative_prompt: str=None, 
        aspect_ratio: str=None, 
        repeat: int=1
    ):
        await interaction.response.defer()
        
        # obtain image
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
        except Exception as e:
            await interaction.followup.send(
                f"Image failed to load. ({e})", 
                ephemeral=True
            )
            return

        await self.generate_image(
            interaction, 
            style, 
            negative_prompt, 
            aspect_ratio, 
            repeat, 
            {
                "name": f"controlnet_{preprocessor}",
                "conditioning": image
            }
        )
    
    @app_commands.command(name="preprocess")
    @app_commands.choices(
        preprocessor=[app_commands.Choice(name=preprocessor, value=preprocessor) for preprocessor in preprocessors.keys()]
    )
    async def preprocessCommand(self, interaction: discord.Interaction, image_url: str, preprocessor: str):
        await interaction.response.defer()
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
        except Exception as e:
            await interaction.response.send_message(f"Image failed to load. ({e})", ephemeral=True)
            return

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
            case "Openpose (Hands Only)":
                preprocessed = await loop.run_in_executor(None, lambda: openposeHandPreprocessor(arr_image, to_pil=True))
                is_PIL = True
            case "Openpose (With Face)":
                preprocessed = await loop.run_in_executor(None, lambda: openposeFacePreprocessor(arr_image, to_pil=True))
                is_PIL = True
            case "Openpose (Full)":
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

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        # I'll deal with this later...
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
            negative_prompt = None
            for field in fields:
                if(field.name == "Negative Prompt"):
                    negative_prompt = field.value
                    break
            aspect_ratio = ""
            for field in fields:
                if(field.name == "Quantized Aspect Ratio"):
                    aspect_ratio = field.value
                    break
            style = "Enhance"
            for field in fields:
                if(field.name == "Style" and field.value != "None" and field.value != None):
                    style = field.value
                    break
            template = style_dict[style]
            true_prompt = template["positive"].format(prompt=prompt)
            true_negative_prompt = negative_prompt
            if(negative_prompt != None):
                true_negative_prompt = template["negative"] + f", {negative_prompt}"

            # create embed
            embed = ImageEmbed("Upscale Job", (128, 0, 255), prompt, style if style != "Enhance" else None, negative_prompt, aspect_ratio, aspect_ratio, (1024, 1024))

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
            except Exception as e:
                await interaction.followup.send("Failed to get image.", ephemeral=True)
                await initial_message.delete()
                print(e)
                return
            image_binary = response.content
            image = Image.open(io.BytesIO(image_binary))
            embed.set_field_at(
                4,
                name="Original Resolution",
                value=f"{image.width // 2}x{image.height // 2}",
                inline=True
            )
            embed.set_field_at(
                5,
                name="New Resolution",
                value=f"{image.width}x{image.height}",
                inline=True
            )
            embed.remove_field(6)
            await initial_message.edit(embed=embed)

            # crop image
            cropped_image = Image.new("RGB", (image.width // 2, image.height // 2))
            top, left = 0, 0
            if(custom_id == "upscale_1"):
                top = image.width // -2
            if(custom_id == "upscale_2"):
                left = image.height // -2
            if(custom_id == "upscale_3"):
                left, top = image.width // -2, image.height // -2
            cropped_image.paste(image, (top, left))

            # send runpod request
            # buffer = io.BytesIO()
            # cropped_image.save(buffer, format="PNG")
            # cropped_image.save("./to_be_upscaled.png", format="PNG")
            # buffer.seek(0)
            # sent_file = base64.b64encode(buffer.getvalue()).decode()
            with io.BytesIO() as image_binary:
                cropped_image.save(image_binary, format="PNG")
                image_binary.seek(0)
                sent_file = base64.b64encode(image_binary.getvalue()).decode()
            payload = {
                "prompt": prompt,
                "image": sent_file,
                "scale": 2
            }
            run_request = upscale.run(payload)
            request_metadata = {
                "message": initial_message,
                "runpod_request": run_request,
                "progress_started": False,
                "embed": embed,
                "uploaded": False
            }
            await awaitResponse(request_metadata, userid, None)