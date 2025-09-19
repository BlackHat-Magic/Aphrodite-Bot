# from controlnet_aux.processor import Processor
from awaitResponse import awaitResponse
from discord import app_commands
from discord.ext import commands
from ui_utils import ImageEmbed
from dotenv import load_dotenv
from PIL import Image
import discord, runpod, asyncio, json, os, io, base64, cv2, numpy, requests

# set up environment variables
load_dotenv()
runpod.api_key = os.getenv("RUNPOD_API_KEY")
# generic = runpod.Endpoint(os.getenv("RUNPOD_GENERIC_ENDPOINT"))
flux = runpod.Endpoint(os.getenv("RUNPOD_FLUX_ENDPOINT"))
schnell = runpod.Endpoint(os.getenv("RUNPOD_SCHNELL_ENDPOINT"))
upscale = runpod.Endpoint(os.getenv("RUNPOD_UPSCALE_ENDPOINT"))
# controlnet = runpod.Endpoint(os.getenv("RUNPOD_CONTROLNET_ENDPOINT"))

supported_ratios = {
    "9:21":  (640, 1536),
    "1:2":   (704, 1472),
    "9:16":  (768, 1344),
    "2:3":   (832, 1280),
    "13:19": (832, 1216),
    "8:11":  (896, 1216),
    "3:4":   (896, 1152),
    "7:9":   (896, 1152),
    "1:1":   (1024, 1024),
    "9:7":   (1152, 896),
    "4:3":   (1152, 896),
    "11:8":  (1216, 896),
    "19:13": (1216, 832),
    "3:2":   (1280, 832),
    "16:9":  (1344, 768),
    "2:1":   (1472, 704),
    "21:9":  (1536, 640)
}

class ImageCog(commands.Cog):
    def __init__(self, client):
        self.client = client
    async def generate_image(
        self,
        interaction: discord.Interaction, 
        prompt: str, 
        negative_prompt: str=None, 
        aspect_ratio: str=1.0, 
        repeat: int=1, 
        conditioning: dict=None,
        model: str=None,
        request_type: str="image"
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
        
        # aspect ratio
        res_info = supported_ratios[aspect_ratio]
        width, height = res_info

        cn_model = None
        if(request_type == "controlnet"):
            cn_model = conditioning["name"].split("_")[0]
            conditioning_image = conditioning["conditioning"]
            image = conditioning.get("image", None)
            if(image):
                statsus = "Controlnet Inpaint Job"
            else:
                statsus = "Controlnet Job"
            color = (255, 128, 0)
        elif(request_type == "upscale"):
            image = conditioning["image"]
            color = (128, 0, 255)
            statsus = "Upscale Job"
            width *= 4
            height *= 4
        elif(request_type == "inpaint"):
            image = conditioning["image"]
            mask = conditioning["mask"]
            color = (255, 255, 255)
            statsus = "Inpaint Job"
        elif(request_type == "outpaint"):
            image = conditioning["image"]
            color = (128, 128, 128)
            statsus = "Outpaint Job"
        else:
            color = (0, 255, 255)
            statsus = "Image Job"

        userid = interaction.user.id
        repetitions = []

        # repetitions
        for i in range(repeat):
            # send embed
            embed = ImageEmbed(
                statsus, 
                color, 
                prompt, 
                aspect_ratio,
                (width, height)
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
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "image_id": conditioning.get("image", None),
                "model": cn_model,
            }
            if(request_type == "controlnet"):
                run_request = controlnet.run(payload)
            elif(request_type == "upscale"):
                run_request = upscale.run(payload)
            elif(model in ["flux", None]):
                run_request = flux.run(payload)
            elif(model == "schnell"):
                run_request = schnell.run(payload)
            else:
                initial_message.edit(
                    content="Unrecognized model.",
                    embed=None,
                    view=None
                )
            repetitions.append({
                "message": initial_message,
                "runpod_request": run_request,
                "progress_started": False,
                "embed": embed,
                "uploaded": False
            })

        await asyncio.gather(*(awaitResponse(repetition, userid, "upscale" if statsus != "Upscale Job" else None) for repetition in repetitions))
    
    @app_commands.command(name="imagine")
    @app_commands.choices(
        aspect_ratio=[app_commands.Choice(name=ratio, value=ratio) for ratio in supported_ratios.keys()]
    )
    async def imagine(
        self,
        interaction: discord.Interaction, 
        prompt: str, 
        aspect_ratio: str="1:1", 
        repeat: int=1
    ):
        await interaction.response.defer()
        await self.generate_image(
            interaction, 
            prompt,
            None, 
            aspect_ratio, 
            repeat, 
            {},
            "schnell"
        )
    
    @app_commands.command(name="flux")
    @app_commands.choices(
        aspect_ratio=[app_commands.Choice(name=ratio, value=ratio) for ratio in supported_ratios.keys()]
    )
    async def flux(
        self,
        interaction: discord.Interaction, 
        prompt: str, 
        aspect_ratio: str="1:1", 
        repeat: int=1
    ):
        await interaction.response.defer()
        await self.generate_image(
            interaction, 
            prompt,
            None, 
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
        request_type, url = custom_id.split(" ")
        # check if it's an upscale request
        if(request_type == "upscale"):
            await interaction.response.defer()
            # get message data
            fields  = message.embeds[0].fields
            prompt = None

            # grab prompt
            for field in fields:
                if(field.name == "Prompt"):
                    prompt = field.value
                    break
            if(prompt == None):
                await interaction.followup.send("Unable to load prompt from original message.", ephemeral=True)
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
                if(field.name == "Aspect Ratio"):
                    aspect_ratio = field.value
                    break

            # generation request
            await self.generate_image(
                interaction=interaction,
                prompt=prompt,
                negative_prompt=negative_prompt,
                aspect_ratio=aspect_ratio,
                repeat=1,
                conditioning={
                    "conditioning": url,
                    "image": url
                },
                model=None,
                request_type="upscale"
            )