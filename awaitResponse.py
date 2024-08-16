from ui_utils import ImageButtons
from PIL import Image
import asyncio, io, base64, discord

async def awaitResponse(repetition, userid, buttons):
    while(True):
        # get request info
        initial_message = repetition["message"]
        status = repetition["runpod_request"].status()
        embed = repetition["embed"]

        # if request is in progress, make sure the user knows
        if(status == "IN_PROGRESS" and not repetition["progress_started"]):
            embed.set_field_at(0, name="Status", value="In progress...")
            repetition["progress_started"] = True
            await initial_message.edit(embed=embed)

        # when the request completes...
        if(status == "COMPLETED" and not repetition["uploaded"]):
            # inform user images are loading
            embed.set_field_at(0, name="Status", value="Loading images...")
            await initial_message.edit(embed=embed)

            # get raw output
            output = repetition["runpod_request"].output()

            # if there's only one image...
            if(type(output) != list):
                output = [output]
                # try to load the image from s3 URL
                try:
                    response = requests.get(output)
                    response.raise_for_status()
                    images = [Image.open(io.BytesIO(response.content))]
                # else inform the user of the error and break
                except Exception as e:
                    initial_message.edit(
                        content=f"Error retrieving output image: {e}",
                        ephemeral=True,
                        embed=None,
                        view=None
                    )
                    break
            # if there's multiple images...
            else:
                # try to load
                try:
                    response = requests.get(output)
                    response.raise_for_status
                    images = [Image.open(io.BytesIO(item.content)) for item in response.content]
                # inform of error otherwise
                except Exception as e:
                    initial_message.edit(
                        content=f"Error retrieving output images: {e}",
                        ephemeral=True,
                        embed=None,
                        view=None
                    )
                    break
            
            # create image grid
            width, height = images[0].size
            if(len(images) == 1):
                grid = images[0]
            else:
                grid = Image.new("RGB", (width * 2, height * 2))
                grid.paste(images[0], (0, 0))
                grid.paste(images[1], (width, 0))
                grid.paste(images[2], (0, height))
                grid.paste(images[3], (width, height))

            # prepare file to send to Discord
            with io.BytesIO() as image_binary:
                grid.save(image_binary, "PNG")
                image_binary.seek(0)
                sent_file = discord.File(fp=image_binary, filename="grid.png")

            # send image and update embed
            await initial_message.add_files(sent_file)
            embed.set_field_at(0, name="Status", value="Completed")
            if(buttons == "upscale"):
                view = ImageButtons(output)
            else:
                view = None
            await initial_message.edit(
                content=f"<@{userid}> Request completed.",
                embed=embed,
                view=view
            )
            repetition["uploaded"] = True
            break
    
        # if request fails, inform user
        if(status in ["FAILED", "ERROR"] and not repetition["uploaded"]):
            repetition["uploaded"] = True
            await initial_message.edit(
                content="Image generation failed.",
                embed=None,
                view=None,
                ephemeral=True
            )
            break
        await asyncio.sleep(1)