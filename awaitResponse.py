from ui_utils import ImageButtons
from PIL import Image
import asyncio, io, base64, discord

async def awaitResponse(repetition, userid, buttons):
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
            if(buttons == "upscale"):
                view = ImageButtons()
            else:
                view = None
            await initial_message.edit(
                content=f"<@{userid}> Request completed.",
                embed=embed,
                view=view
            )
            repetition["uploaded"] = True
            break
        await asyncio.sleep(1)