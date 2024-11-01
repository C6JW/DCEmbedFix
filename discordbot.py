import discord
from aiohttp.hdrs import SERVER
from discord.ext import commands
import re
import os
from dotenv import load_dotenv
import requests

load_dotenv()

TOKEN = os.getenv('BOTTOKEN')
SERVER_DOMAIN = os.getenv('SERVER_DOMAIN') + "/?url="
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

pattern = r"(https?://(?:gall|m|enter)\.dcinside\.com/[^ ?]+(?:\?id=[^ &]+&no=[^ &]*)?)(?:\?recommend=\d+)?(?:&s_type=[^ &]+&s_keyword=[^ &]*&page=\d+)?"

def modify_links(message_content):
    print("called")
    modified_message = re.sub(
        pattern,
        lambda match: f"[{match.group(1).replace('https://', '').replace('http://', '')}]({SERVER_DOMAIN}{match.group(1)})",
        message_content
    )
    print(modified_message)
    return modified_message
"".removeprefix("https://")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    modified_message = modify_links(message.content)
    if message.content != modified_message:
        await message.channel.send(modified_message)

@client.event
async def on_guild_join(guild):
    # Iterate through each text channel in the guild
    for channel in guild.text_channels:
        # Check if the bot has permission to create webhooks in the channel
        if channel.permissions_for(guild.me).manage_webhooks:
            # Create a webhook
            webhook = await channel.create_webhook(name=f'{guild.name} Webhook')
            print(f'Created webhook {webhook.name} in {channel.name}')
client.run(TOKEN)
