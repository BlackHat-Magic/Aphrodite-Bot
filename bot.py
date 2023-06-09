# from discord.ext import commands, ipc
# from discord import app_commands
from dotenv import load_dotenv
import discord, os, openai, tiktoken, re

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
system_prompt = ""
with open("system_prompt_main.txt", "r") as file:
    system_prompt += file.read()
thread_namer = ""
with open("system_prompt_name_thread.txt", "r") as file:
    thread_namer += file.read()

# class chatBot(discord.Client):
#     def __init__(self):
#         super().__init(intent=discord.Intents.default())
#         self.synced = False

#     async def on_ready(self):
#         await self.wait_until_ready()
#         if(not self.synced):
#             await tree.sync(guild = discord.Object(id=os.getenv("GUILD_ID")))
#             self.synced = True
#         print(f"Logged in as {self.user}.")

# client = chatBot()
# tree = app_commands.CommandTree(client)

# @tree.command(name="test", description="testing", guild=discord.Object(id=os.getenv("GUILD_ID")))
# async def self(interaction: discord.Interaction, name:str):
#     await interaction.response.send_message(f"Hello {name}", ephemeral=True)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}.")

@client.event
async def on_message(message):
    if(message.author == client.user):
        return
    if(client.user in message.mentions):
        print("Client Mentioned.")
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
                    print("bot message")
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
            while len(encoding.encode("".join([f"{message['role']} {message['content']}\n" for message in gpt_convo]))) > 3072:
                gpt_convo.pop(1)
            print(f"Truncated Conversation to {len(gpt_convo)} messages")
            
            # Obtain ClosedAI response
            print("Obtaining ClosedAI response...")
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=gpt_convo
            )
            # reduce size until fits within context length
            await message.reply(response["choices"][0]["message"]["content"])

client.run(os.getenv("DISCORD_CLIENT_TOKEN"))