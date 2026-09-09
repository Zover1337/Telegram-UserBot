__MODULE__ = "Финансы 💸"
__HELP__ = "<code>.usd</code> — Курс доляра\n<code>.ton</code> — Курс TON"

import asyncio
import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import ONLY_ME, PREFIXES, usa_emoji, usd_emoji, greenc_emoji, redc_emoji, up_emoji, ton_emoji, rocket_emoji, down_emoji

@Client.on_message(filters.command("usd", prefixes=PREFIXES) & ONLY_ME)
async def usd_handler(_, msg: Message):
    try:
        await msg.edit("💸 <i>Звоню на Уолл-стрит...</i>")
        await asyncio.sleep(0.5)
        await msg.edit("📉 <i>Смотрю котировки...</i>")
        await asyncio.sleep(0.5)

        url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=rub&include_24hr_change=true"
        r = requests.get(url).json()

        price = r['tether']['rub']
        change = r['tether']['rub_24h_change']

        trend_emoji = greenc_emoji if change > 0 else redc_emoji
        trend = f'<emoji id="{trend_emoji}">{"🟢" if change > 0 else "🔴"}</emoji>'
        sign = "+" if change > 0 else ""

        text = (
            f'<emoji id="{usa_emoji}">🇺🇸</emoji> <b>USD</b>\n'
            f'<emoji id="{usd_emoji}">💰</emoji> Цена: <b>{price:.2f} RUB</b>\n'
            f'<emoji id="{up_emoji}">📊</emoji> За 24ч: {trend} <b>{sign}{change:.2f}%</b>'
        )
        await msg.edit(text)
    except Exception as e:
        await msg.edit(f"❌ Биржа упала: {e}")


@Client.on_message(filters.command("ton", prefixes=PREFIXES) & ONLY_ME)
async def ton_handler(_, msg: Message):
    frames = ["📲 <i>Набираю Паше...</i>", "📲 <i>Набираю Паше...</i> 📞", "🗣 <i>Паш, че там по графикам?</i>", "🗣 <i>Ага, понял, ща передам.</i>"]
    for f in frames:
        try:
            await msg.edit(f)
            await asyncio.sleep(0.5)
        except:
            pass

    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd&include_24hr_change=true"
        r = requests.get(url).json()

        price = r['the-open-network']['usd']
        change = r['the-open-network']['usd_24h_change']

        trend_emoji = rocket_emoji if change > 0 else down_emoji
        trend = f'<emoji id="{trend_emoji}">{"🚀" if change > 0 else "🔻"}</emoji>'
        sign = "+" if change > 0 else ""

        text = (
            f'<emoji id="{ton_emoji}">💎</emoji> <b>TON</b>\n'
            f'<emoji id="{usd_emoji}">💵</emoji> Цена: <b>{price:.2f} USD</b>\n'
            f'<emoji id="{up_emoji}">📊</emoji> Динамика: {trend} <b>{sign}{change:.2f}%</b>'
        )
        await msg.edit(text)
    except Exception as e:
        await msg.edit(f"❌ Абонент недоступен: {e}")
