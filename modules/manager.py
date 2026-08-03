__MODULE__ = "Управление ⚙️"
__HELP__ = "<code>.dlmod [reply]</code> — Установить модуль\n<code>.delmod [name]</code> — Удалить модуль\n<code>.restart</code> — Рестарт"

import os
import sys
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import ONLY_ME

@Client.on_message(filters.command("restart", prefixes=".") & ONLY_ME)
async def restart_handler(_, msg: Message):
    await msg.edit("🔄 Перезапускаю юзербота...")
    os.execl(sys.executable, sys.executable, *sys.argv)

@Client.on_message(filters.command("dlmod", prefixes=".") & ONLY_ME)
async def dlmod_handler(client: Client, msg: Message):
    if not msg.reply_to_message or not msg.reply_to_message.document:
        await msg.edit("❌ Ответьте на файл модуля (.py), чтобы установить его.")
        return
        
    doc = msg.reply_to_message.document
    if not doc.file_name.endswith(".py"):
        await msg.edit("❌ Это не файл модуля Python (.py).")
        return
        
    await msg.edit(f"📥 Скачиваю модуль <code>{doc.file_name}</code>...")
    
    file_path = os.path.join("modules", doc.file_name)
    await client.download_media(msg.reply_to_message, file_name=file_path)
    
    await msg.edit(f"✅ Модуль <b>{doc.file_name}</b> установлен! Перезапускаю...")
    os.execl(sys.executable, sys.executable, *sys.argv)

@Client.on_message(filters.command("delmod", prefixes=".") & ONLY_ME)
async def delmod_handler(_, msg: Message):
    if len(msg.command) < 2:
        await msg.edit("❌ Укажите название модуля для удаления (без .py). Пример: <code>.delmod poland</code>")
        return
        
    mod_name = msg.text.split(maxsplit=1)[1]
    if not mod_name.endswith(".py"):
        mod_name += ".py"
        
    file_path = os.path.join("modules", mod_name)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        await msg.edit(f"🗑 Модуль <b>{mod_name}</b> удален! Перезапускаю...")
        os.execl(sys.executable, sys.executable, *sys.argv)
    else:
        await msg.edit(f"❌ Модуль <b>{mod_name}</b> не найден.")
