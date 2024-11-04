from flask import Flask, request, request, redirect, render_template_string
import discord
from discord import Webhook
from discord_webhook import DiscordWebhook
from aiohttp.hdrs import SERVER
from discord.ext import commands
import re
import os
from dotenv import load_dotenv
import requests
import aiohttp
import asyncio
import tempfile
import json
from bs4 import BeautifulSoup
import httpx
from bs4 import BeautifulSoup
import logging

load_dotenv()

TOKEN = os.getenv('BOTTOKEN')
SERVER_DOMAIN = os.getenv('SERVER_DOMAIN') + "/?url="

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
client = discord.Client(intents=intents)

app = Flask(__name__)
logging.basicConfig(level=logging.CRITICAL)

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

def fetch_with_httpx(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
    }
    try:
        with httpx.Client(verify=False, follow_redirects=True) as client:
            response = client.get(url, headers=headers, timeout=5)
            response.raise_for_status()
        return response.text
    except httpx.RequestError as e:
        logging.error(f"Failed to retrieve the page: {e}")
        return None

@client.event
async def on_message(message):
    if message.author == client.user or message.webhook_id is not None:
        return

    webhook = await ensure_webhook(message.channel)



    if ".dcinside.com" in message.content:
        urls = [part for part in message.content.split() if ".dcinside.com" in part]
        url = urls[0]
        page_content = fetch_with_httpx(url)
        soup = BeautifulSoup(page_content, 'html.parser')
        title = soup.find('title').text if soup.find('title') else "No Title"
        description = soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {
            'name': 'description'}) else "No Description"
        #image = soup.find('meta', {'property': 'og:image'})['content'] if soup.find('meta', {
            #'property': 'og:image'}) else "https://static.wikia.nocookie.net/joke-battles/images/d/df/Gigachad.png/revision/latest/scale-to-width-down/340?cb=20230812064835"
        appending_file = soup.find(class_='appending_file')
        if appending_file:
            first_link = appending_file.find('a', href=True)['href']
            print(first_link)
            image=first_link

        username = message.author.display_name
        avatar_url = message.author.avatar.url if message.author.avatar else None
        files = await process_attachments(message.attachments)

        embed = discord.Embed(
            title=title,
            url=url,
            description=description
        )

        await send_webhook_message(webhook, message.content, username, avatar_url, files, embed, image=None)
        await message.delete()

async def process_attachments(attachments):
    files = []
    for attachment in attachments:
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as response:
                if response.status == 200:
                    temp_file = tempfile.NamedTemporaryFile(delete=False)
                    temp_file.write(await response.read())
                    temp_file.close()
                    files.append(discord.File(temp_file.name, filename=attachment.filename))
    return files

async def send_webhook_message(target_webhook, content, username, avatar_url, files, embed, image):
    form_data = aiohttp.FormData()  # Create a FormData object
    payload = {
        "content": content,
        "embeds": [{
            "title": embed.title,
            "url": embed.url,
            "description": embed.description,
            "image": {
                "url": image
            }
        }] if embed else [],
        "username": username,
        "avatar_url": avatar_url
    }
    form_data.add_field("payload_json", json.dumps(payload))

    # Add each file as a sequentially numbered file field (file0, file1, ...)
    for i, file in enumerate(files):
        form_data.add_field(f"file{i}", open(file.fp.name, 'rb'), filename=file.filename)

    async with aiohttp.ClientSession() as session:
        await session.post(target_webhook.url, data=form_data)

    # Cleanup temporary files
    for file in files:
        file.close()
        os.remove(file.fp.name)


client.run(TOKEN)
