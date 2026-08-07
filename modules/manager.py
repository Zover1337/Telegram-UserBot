__MODULE__ = "Управление ⚙️"
__HELP__ = (
    "<code>.dlmod [reply]</code> — Скачать модуль в карантин и показать SHA256\n"
    "<code>.dlmod confirm [sha256]</code> — Установить проверенный модуль\n"
    "<code>.delmod [name]</code> — Удалить модуль\n"
    "<code>.restart</code> — Рестарт"
)

import os
import sys
import html
import hashlib
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import ONLY_ME
from paths import MODULES_DIR, PENDING_DIR, safe_module_path

# ponytail: карантин в памяти, теряется при рестарте — подтверждать сразу после .dlmod
_pending = {}

@Client.on_message(filters.command("restart", prefixes=".") & ONLY_ME)
async def restart_handler(_, msg: Message):
    await msg.edit("🔄 Перезапускаю юзербота...")
    os.execl(sys.executable, sys.executable, *sys.argv)

@Client.on_message(filters.command("dlmod", prefixes=".") & ONLY_ME)
async def dlmod_handler(client: Client, msg: Message):
    args = msg.command[1:]
    if args and args[0] == "confirm":
        await install_pending(msg, args[1] if len(args) > 1 else "")
        return

    if not msg.reply_to_message or not msg.reply_to_message.document:
        await msg.edit("❌ Ответьте на файл модуля (.py), чтобы установить его.")
        return

    doc = msg.reply_to_message.document
    path = safe_module_path(doc.file_name, PENDING_DIR)
    if not path:
        await msg.edit("❌ Недопустимое имя модуля. Ожидается простое имя вида <code>name.py</code>.")
        return

    name = os.path.basename(path)
    await msg.edit(f"📥 Скачиваю модуль <code>{html.escape(name)}</code>...")

    buf = await client.download_media(msg.reply_to_message, in_memory=True)
    data = bytes(buf.getbuffer())

    os.makedirs(PENDING_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

    digest = hashlib.sha256(data).hexdigest()
    _pending[digest] = path
    preview = html.escape(data[:400].decode("utf-8", "replace"))

    await msg.edit(
        f"⚠️ Модуль <code>{html.escape(name)}</code> скачан в карантин и <b>не установлен</b>.\n"
        f"Размер: <b>{len(data)}</b> байт\n"
        f"SHA256: <code>{digest}</code>\n\n"
        f"<b>Начало файла:</b>\n<pre>{preview}</pre>\n"
        f"Прочитайте код целиком — после установки он выполнится с вашими правами.\n"
        f"Установить: <code>.dlmod confirm {digest}</code>"
    )

async def install_pending(msg: Message, digest: str):
    src = _pending.get(digest)
    if not src or not os.path.exists(src):
        await msg.edit("❌ Модуль с таким SHA256 не найден. Сначала <code>.dlmod</code> в ответ на файл.")
        return

    with open(src, "rb") as f:
        data = f.read()
    if hashlib.sha256(data).hexdigest() != digest:
        _pending.pop(digest, None)
        await msg.edit(
            "❌ Содержимое файла в карантине изменилось после проверки — установка отменена.\n"
            "Скачайте модуль заново через <code>.dlmod</code>."
        )
        return

    dst = safe_module_path(os.path.basename(src), MODULES_DIR)
    if not dst:
        await msg.edit("❌ Недопустимое имя модуля.")
        return

    os.makedirs(MODULES_DIR, exist_ok=True)
    os.replace(src, dst)
    _pending.pop(digest, None)

    await msg.edit(f"✅ Модуль <b>{html.escape(os.path.basename(dst))}</b> установлен! Перезапускаю...")
    os.execl(sys.executable, sys.executable, *sys.argv)

@Client.on_message(filters.command("delmod", prefixes=".") & ONLY_ME)
async def delmod_handler(_, msg: Message):
    if len(msg.command) < 2:
        await msg.edit("❌ Укажите название модуля для удаления (без .py). Пример: <code>.delmod poland</code>")
        return

    mod_name = msg.text.split(maxsplit=1)[1]
    if not mod_name.endswith(".py"):
        mod_name += ".py"

    file_path = safe_module_path(mod_name, MODULES_DIR)
    if not file_path:
        await msg.edit("❌ Недопустимое имя модуля.")
        return

    if os.path.exists(file_path):
        os.remove(file_path)
        await msg.edit(f"🗑 Модуль <b>{html.escape(os.path.basename(file_path))}</b> удален! Перезапускаю...")
        os.execl(sys.executable, sys.executable, *sys.argv)
    else:
        await msg.edit(f"❌ Модуль <b>{html.escape(os.path.basename(file_path))}</b> не найден.")
