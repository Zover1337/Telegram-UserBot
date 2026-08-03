__MODULE__ = "Помощь ℹ️"
__HELP__ = "<code>.help</code> — Показать это меню"

import os
import sys
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import ONLY_ME, zamok_emoji

@Client.on_message(filters.command("help", prefixes=".") & ONLY_ME)
async def help_handler(_, msg: Message):
    text = f'<b>Userbot by Zover v1.0 (Release)</b>\n\n'
    
    modules_dir = "modules"
    loaded_modules = []
    
    if os.path.exists(modules_dir):
        for file in sorted(os.listdir(modules_dir)):
            if file.endswith(".py") and not file.startswith("_"):
                mod_name = file[:-3]
                mod = sys.modules.get(f"modules.{mod_name}")
                if mod and hasattr(mod, "__HELP__"):
                    mod_title = getattr(mod, "__MODULE__", mod_name.capitalize())
                    loaded_modules.append(f"<b>{mod_title}</b>:\n{mod.__HELP__}")
                    
    if loaded_modules:
        text += "\n\n".join(loaded_modules)
    else:
        text += "<i>Нет загруженных модулей с описанием.</i>"
        
    await msg.edit(text)
