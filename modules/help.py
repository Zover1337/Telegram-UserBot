from pyrogram import Client, filters
from pyrogram.types import Message
from utils import ONLY_ME, zamok_emoji, usa_emoji, ton_emoji, internet_emoji, spotify_emoji

@Client.on_message(filters.command("help", prefixes=".") & ONLY_ME)
async def help_handler(_, msg: Message):
    text = f"""
<emoji id="{zamok_emoji}">🔒</emoji> <b>Private Userbot v2.1</b>

<code>.tt &lt;link&gt;</code> — Скачать TikTok
<code>.usd</code> — Курс доляра <emoji id="{usa_emoji}">🇺🇸</emoji>
<code>.ton</code> — Курс TON <emoji id="{ton_emoji}">💎</emoji>
<code>.poland</code> — Шутка про Польшу
<code>.rand_anec</code> — Чёрный анекдотик
<code>.weather</code> — Погода в мск
<code>.weather [Город]</code> — Погода в другом городе
<code>.spotify</code> — Какой трек сейчас играет <emoji id="{spotify_emoji}">🎧</emoji>

<emoji id="{internet_emoji}">🌐</emoji> <b>VPN:</b>
<code>.vpn_help</code> — Частые вопросы
<code>.vpn_apps</code> — Клиенты для работы
<code>.requisites</code> — Реквизиты для оплаты

<b>Модули:</b>
<code>.dlmod [reply to file]</code> — Установить модуль
<code>.delmod [module_name]</code> — Удалить модуль
<code>.restart</code> — Перезапустить юзербота
    """
    await msg.edit(text)
