import os
import discord
from discord.ext import commands
from discord import Webhook
from flask import Flask, request, redirect, render_template_string
import requests
import aiohttp
import asyncio
import tempfile
import json
import httpx
from bs4 import BeautifulSoup
import logging
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

TOKEN = os.getenv('BOTTOKEN_TEST')
SERVER_DOMAIN = os.getenv('SERVER_DOMAIN') + "/?url="

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
client = discord.Client(intents=intents)

app = Flask(__name__)
logging.basicConfig(level=logging.CRITICAL)

message_author_map = {}

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


# Make this an async function by using httpx.AsyncClient
async def fetch_with_httpx(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
    }
    try:
        async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=5)
            response.raise_for_status()
        return response.text
    except httpx.RequestError as e:
        logging.error(f"Failed to retrieve the page: {e}")
        return None


async def get_og_url(url):
    # First, try fetching the page content using httpx
    page_content = await fetch_with_httpx(url)

    # Parse the page content using BeautifulSoup
    soup = BeautifulSoup(page_content, 'html.parser')

    # Look for the Open Graph URL (og:url) meta tag
    og_url = soup.find("meta", property="og:url")

    # If we find the og:url, return it; otherwise, fall back to Playwright to get the final URL
    if og_url:
        return og_url["content"]
    else:
        print("OG URL not found")
        # If OG URL not found, use Playwright to resolve the final URL
        return await get_final_url_with_playwright(url)


# Fetch the final URL using Playwright (in case there's a redirect)
async def get_final_url_with_playwright(url):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url)
            final_url = page.url
            await browser.close()
        return final_url
    except Exception as e:
        logging.error(f"Failed to resolve final URL using Playwright: {e}")
        return url  # Return original URL if something fails


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
                "url": "https://nstatic.dcinside.com/dc/w/images/logo_icon.ico"
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
        async with session.post(target_webhook.url, data=form_data) as response:
            if response.status == 204:
                # Fetch the last sent message for tracking
                async for msg in target_webhook.channel.history(limit=1):
                    return msg  # Return the last sent message
            else:
                raise Exception(f"Failed to send message via webhook: {response.status}")
    return None

@client.event
async def on_message(message):
    if message.author == client.user or message.webhook_id is not None:
        return

    if ".dcinside.com" in message.content:
        urls = [part for part in message.content.split() if ".dcinside.com" in part]
        url = urls[0]

        # Get OG URL (using httpx first, fallback to Playwright if necessary)
        og_url = await get_og_url(url)
        url = og_url

        page_content = await fetch_with_httpx(og_url)
        soup = BeautifulSoup(page_content, 'html.parser')

        title = soup.find('title').text if soup.find('title') else "No Title"
        description = soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {
            'name': 'description'}) else "No Description"

        appending_file = soup.find(class_='appending_file')
        image = None
        if appending_file:
            first_link = appending_file.find('a', href=True)['href']
            image = first_link

        username = message.author.display_name
        avatar_url = message.author.avatar.url if message.author.avatar else None
        files = await process_attachments(message.attachments)

        embed = discord.Embed(
            title=title,
            url=og_url,
            description=description
        )

        webhook = await ensure_webhook(message.channel)
        sent_message = await send_webhook_message(webhook, message.content, username, avatar_url, files, embed, image=None)
        await message.delete()
        if sent_message:
            message_author_map[sent_message.id] = message.author.id
            await sent_message.add_reaction("❌")


@client.event
async def on_raw_reaction_add(payload):
    if payload.emoji.name == "❌":  # Check for the 'X' emoji
        message_id = payload.message_id
        user_id = payload.user_id

        # Check if the message is in the map and the reacting user is the original author
        if message_id in message_author_map and message_author_map[message_id] == user_id:
            channel = client.get_channel(payload.channel_id)
            if channel:
                message = await channel.fetch_message(message_id)
                if message:
                    await message.delete()
                    del message_author_map[message_id]  # Remove entry from the map


client.run(TOKEN)

