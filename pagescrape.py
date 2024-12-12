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

app = Flask(__name__)
logging.basicConfig(level=logging.CRITICAL)

