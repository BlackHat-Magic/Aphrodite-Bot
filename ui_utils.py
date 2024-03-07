from discord.ui import Button, Select, select, button
from discord import ButtonStyle, SelectOption
import discord

class ImageEmbed(discord.Embed):
    def __init__(self, title, rgb, prompt, style, negative_prompt, aspect_ratio, quantized_aspect_ratio, resolution):
        super().__init__(title=title, color=discord.Color.from_rgb(*(rgb)))
        self.add_field(name="Status", value="In queue...", inline=True)
        self.add_field(name="Prompt", value=prompt, inline=False)
        self.add_field(name="Style", value=style if style else "None", inline=False)
        self.add_field(name="Negative Prompt", value=negative_prompt if negative_prompt else "N/A", inline=False)
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

class ImageButtons(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.upscaled_urls = [None, None, None, None]
        self.add_item(Button(style=ButtonStyle.primary, label="U1", custom_id="upscale_0", row=0, emoji="↕"))
        self.add_item(Button(style=ButtonStyle.primary, label="U2", custom_id="upscale_1", row=0, emoji="↕"))
        self.add_item(Button(style=ButtonStyle.primary, label="U3", custom_id="upscale_2", row=1, emoji="↕"))
        self.add_item(Button(style=ButtonStyle.primary, label="U4", custom_id="upscale_3", row=1, emoji="↕"))