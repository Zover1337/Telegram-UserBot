import asyncio
import random
import requests
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import ONLY_ME, black_emoji

@Client.on_message(filters.command("rand_anec", prefixes=".") & ONLY_ME)
async def anec_handler(_, msg: Message):
    bars = ["💾 Ищу в базе: [🟥⬜️⬜️]", "💾 Ищу в базе: [🟥🟥⬜️]", "💾 Ищу в базе: [🟥🟥🟥]"]
    for b in bars:
        try:
            await msg.edit(b)
            await asyncio.sleep(0.2)
        except:
            pass

    try:
        page = random.randint(1, 5)
        r = requests.get(f"https://4tob.ru/anekdots/tag/black/page{page}")
        soup = BeautifulSoup(r.text, 'html.parser')

        jokes = soup.find_all("div", class_="q")
        if not jokes:
            await msg.edit("Пусто :(")
            return

        joke = random.choice(jokes)
        nomer = joke.find("div", class_="nomer").a.text if joke.find("div", class_="nomer") else "Анекдот"
        content = joke.find("div", class_="text").get_text(separator="\n").strip()

        await msg.edit(f'<emoji id="{black_emoji}">🏴</emoji> <b>{nomer}</b>\n\n{content}')
    except Exception as e:
        await msg.edit(f"Error: {e}")
