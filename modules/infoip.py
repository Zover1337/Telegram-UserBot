__MODULE__ = "IP information 🌐"
__HELP__ = "<code>.ipi &lt;IP|domain&gt;</code> - Show public IP intelligence"

import asyncio

import aiohttp
import config
from pyrogram import Client, filters
from pyrogram.types import Message

from services.ip_lookup import InvalidTarget, lookup_ip, render_chunks, resolve_target
from utils import ONLY_ME, PREFIXES


@Client.on_message(filters.command("ipi", prefixes=PREFIXES) & ONLY_ME)
async def info_ip_handler(_, msg: Message):
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await msg.edit("Usage: <code>.ipi &lt;IP|domain&gt;</code>")
        return

    try:
        target = await resolve_target(parts[1])
    except InvalidTarget as exc:
        await msg.edit(f"Invalid target: <code>{str(exc)}</code>")
        return

    await msg.edit("Looking up IP information...")
    timeout = aiohttp.ClientTimeout(total=15, connect=5)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        results = await asyncio.gather(*(lookup_ip(session, ip, config) for ip in target.ips))

    chunks = render_chunks(results, target.host)
    await msg.edit(chunks[0], disable_web_page_preview=True)
    for chunk in chunks[1:]:
        await msg.reply_text(chunk, disable_web_page_preview=True)
