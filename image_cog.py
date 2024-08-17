# from controlnet_aux.processor import Processor
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
# generic = runpod.Endpoint(os.getenv("RUNPOD_GENERIC_ENDPOINT"))
flux = runpod.Endpoint(os.getenv("RUNPOD_FLUX_ENDPOINT"))
schnell = runpod.Endpoint(os.getenv("RUNPOD_SCHNELL_ENDPOINT"))
upscale = runpod.Endpoint(os.getenv("RUNPOD_UPSCALE_ENDPOINT"))
# controlnet = runpod.Endpoint(os.getenv("RUNPOD_CONTROLNET_ENDPOINT"))x

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
# depthPreprocessor = Processor("depth_midas")
# openposePreprocessor = Processor("openpose")
# openposeFacePreprocessor = Processor("openpose_face")
# openposeHandPreprocessor = Processor("openpose_hand")
# openposeFullPreprocessor = Processor("openpose_full")
# preprocessors = {
#     "Canny Edge": depthPreprocessor,
#     "Depth Map": openposePreprocessor,
#     "Openpose (With Face)": openposeFacePreprocessor,
#     "Openpose (Hands Only)": openposeHandPreprocessor,
#     "Openpose (Full)": openposeFullPreprocessor
# }

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
        conditioning: dict=None,
        model: str=None
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
        
        # if there is a 'name' key in the conditioning dict
        # that means this is a controlnet job
        cn_model = None
        if("name" in conditioning.keys()):
            image = conditioning["conditioning"]
            if("controlnet" in conditioning["name"]):
                cn_model = conditioning["name"].split("_")[0]
            statsus = "Controlnet Job"
            color = (255, 128, 0)
        # otherwise, the only other type of request that has
        # conditioning is upscaling
        elif(conditioning):
            statsus = "Upscale Job"
            color = (128, 0, 255)
        # if no conditioning, image job
        else:
            statsus = "Image Job"
            color = (0, 255, 255)

        userid = interaction.user.id
        repetitions = []

        # positive prompt
        # if(style == "Enhance" or style == None):
        #     template = style_dict["Enhance"]
        # else:
        #     template = style_dict[style]
        # true_prompt = template["positive"].format(prompt=prompt)

        # negative prompt
        # if(negative_prompt and style != "Raw Prompt"):
        #     true_negative_prompt = f"{template['negative']}, {negative_prompt}"
        # else:
        #     true_negative_prompt = negative_prompt
        
        # aspect ratio
        res_info = min(supported_ratios, key=lambda x:abs(x[0] - aspect_ratio))
        width, height = res_info[2]

        # repetitions
        for i in range(repeat):
            # send embed
            embed = ImageEmbed(
                statsus, 
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
            
            if(model == "flux"):
                num_images = 1
            else:
                num_images = 4

            payload = {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "num_images": num_images,
                "width": width,
                "height": height,
                "images_id": conditioning.get("image", None),
                "model": cn_model
            }
            if(cn_model):
                run_request = controlnet.run(payload)
            elif(conditioning):
                run_request = upscale.run(payload)
            elif(model == "flux"):
                run_request = flux.run(payload)
            elif(model == "schnell"):
                run_request = schnell.run(payload)
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
        aspect_ratio=[app_commands.Choice(name=ratio[1], value=ratio[0]) for ratio in supported_ratios]
    )
    async def imagine(
        self,
        interaction: discord.Interaction, 
        prompt: str, 
        style: str="", 
        negative_prompt: str=None, 
        aspect_ratio: float=1., 
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
            {},
            "schnell"
        )
    
    @app_commands.command(name="flux")
    @app_commands.describe(style="Style your image")
    @app_commands.choices(
        style=[app_commands.Choice(name=style, value=style) for style in styles],
        aspect_ratio=[app_commands.Choice(name=ratio[1], value=ratio[0]) for ratio in supported_ratios]
    )
    async def imagine(
        self,
        interaction: discord.Interaction, 
        prompt: str, 
        style: str="", 
        negative_prompt: str=None, 
        aspect_ratio: float=1., 
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
            {},
            "flux"
        )

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        # I'll deal with this later...
        if(interaction.type != discord.InteractionType.component):
            return
        custom_id = interaction.data["custom_id"]
        message = interaction.message
        userid = interaction.user.id
        # check if it's an upscale request
        return
        if(re.match(f"^upscale_\d$", custom_id)):
            # get message data
            fields  = message.embeds[0].fields
            prompt = None

            # grab prompt
            for field in fields:
                if(field.name == "Prompt"):
                    prompt = field.value
                    break
            if(prompt == None):
                await interaction.response.send_message("Unable to load prompt from original message.", ephemeral=True)
                return
            
            # grab negative prompt
            negative_prompt = None
            for field in fields:
                if(field.name == "Negative Prompt"):
                    negative_prompt = field.value
                    break
            
            # grab aspect ratio
            aspect_ratio = ""
            for field in fields:
                if(field.name == "Quantized Aspect Ratio"):
                    aspect_ratio = field.value
                    break
            if(not aspect_ratio in [ratio[1] for ratio in supported_ratios]):
                aspect_ratio = "1:1"

            # grab style
            style = "Enhance"
            for field in fields:
                if(field.name == "Style" and field.value != "None" and field.value != None):
                    style = field.value
                    break
            
            # grab image
            try:
                response  = requests.get(message.attachments[0].url)
                response.raise_for_status()
            except Exception as e:
                await interaction.followup.send("Failed to get image.", ephemeral=True)
                return
            image_binary = response.content
            image = Image.open(io.BytesIO(image_binary))

            # generation request
            self.generate_image(
                interaction,
                prompt,
                style,
                negative_prompt,
                aspect_ratio,
                1,
                {
                    "name": "upscale",
                    "conditioning": image
                }
            )