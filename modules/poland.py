import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from utils import ONLY_ME

@Client.on_message(filters.command("poland", prefixes=".") & ONLY_ME)
async def poland_handler(_, msg: Message):
    lines = [
        "🇮🇩 — Польша наоборот",
        "🇬🇱 — Польша в Польше",
        "🇱🇧 — новогодняя Польша",
        "🇸🇬 — ночная Польша",
        "🇨🇦 — Польша осенью",
        "🇲🇹 — Польша боком",
        "🇩🇪 — Польша раком"
    ]
    text = ""
    for line in lines:
        text = text + "\n" + line if text else line
        try:
            await msg.edit(text)
            await asyncio.sleep(0.7)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except:
            pass
