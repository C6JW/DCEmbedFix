import discord
from discord import webhook
from aiohttp.hdrs import SERVER
from discord.ext import commands
import re
import os
from dotenv import load_dotenv
import requests
import aiohttp
import asyncio
import tempfile

load_dotenv()

TOKEN = os.getenv('BOTTOKEN')
SERVER_DOMAIN = os.getenv('SERVER_DOMAIN') + "/?url="

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
client = discord.Client(intents=intents)

pattern = r"(https?://(?:gall|m|enter)\.dcinside\.com/[^ ?]+(?:\?id=[^ &]+&no=[^ &]*)?)(?:\?recommend=\d+)?(?:&s_type=[^ &]+&s_keyword=[^ &]*&page=\d+)?"

def modify_links(message_content):
    modified_message = re.sub(
        pattern,
        lambda match: f"[{match.group(1).replace('https://', '').replace('http://', '')}]({SERVER_DOMAIN}{match.group(1)})",
        message_content
    )
    return modified_message

async def fetch_avatar_bytes(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()
            return None

async def ensure_webhook(channel):
    if channel.permissions_for(channel.guild.me).manage_webhooks:
        webhooks = await channel.webhooks()
        bot_webhook = next((w for w in webhooks if w.name == "DCEmbedFixer"), None)

        if not bot_webhook:
            bot_webhook = await channel.create_webhook(name="DCEmbedFixer")
        return bot_webhook


@client.event
async def on_message(message):
    if message.author == client.user or message.webhook_id is not None:
        return

    webhook = await ensure_webhook(message.channel)
    modified_message = modify_links(message.content)

    if message.content != modified_message:
        username = message.author.display_name
        avatar_url = message.author.avatar.url if message.author.avatar else None
        files = await process_attachments(message.attachments)

        await send_webhook_message(webhook, modified_message, username, avatar_url, files)
        await message.delete()

async def process_attachments(attachments):
    """Process message attachments and return a list of Discord File objects."""
    files = []
    for attachment in attachments:
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as response:
                if response.status == 200:
                    # Create a temporary file to store the attachment
                    temp_file = tempfile.NamedTemporaryFile(delete=False)
                    temp_file.write(await response.read())
                    temp_file.close()
                    # Append the discord.File object
                    files.append(discord.File(temp_file.name, filename=attachment.filename))
    return files

async def send_webhook_message(target_webhook, content, username, avatar_url, files):
    form_data = aiohttp.FormData()  # Create a FormData object
    form_data.add_field("username", username)
    form_data.add_field("avatar_url", avatar_url)
    form_data.add_field("content", content)

    # Add files to the FormData
    for file in files:
        form_data.add_field("file", file.fp, filename=file.filename)  # Use the file's pointer and name

    async with aiohttp.ClientSession() as session:
        await session.post(target_webhook.url, data=form_data)

@client.event
async def on_guild_join(guild):
    # Iterate through each text channel in the guild
    for channel in guild.text_channels:
        # Check if the bot has permission to create webhooks in the channel
        if channel.permissions_for(guild.me).manage_webhooks:
            # Create a webhook
            target_webhook = await channel.create_webhook(name="DCEmbedFixer")
            print(f'Created webhook {target_webhook.name} in {channel.name}')

client.run(TOKEN)
