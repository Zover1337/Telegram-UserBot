__MODULE__ = "Base64 🔐"
__HELP__ = (
    "<code>.cbase64 &lt;текст&gt;</code> — Кодировать текст в Base64\n"
    "<code>.dbase64 &lt;Base64&gt;</code> — Декодировать Base64 в текст"
)

import base64
import binascii
import html

from pyrogram import Client, filters
from pyrogram.types import Message

from utils import ONLY_ME, PREFIXES

MAX_RESULT_LENGTH = 3800


def encode_text(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def decode_text(value: str) -> str:
    try:
        return base64.b64decode(value, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Некорректная строка Base64") from exc


def fits_message(value: str) -> bool:
    return len(html.escape(value)) <= MAX_RESULT_LENGTH


def extract_argument(msg: Message) -> str:
    parts = (msg.text or "").split(maxsplit=1)
    return parts[1] if len(parts) == 2 else ""


@Client.on_message(filters.command("cbase64", prefixes=PREFIXES) & ONLY_ME)
async def encode_base64_handler(_, msg: Message):
    value = extract_argument(msg)
    if not value:
        await msg.edit("Укажите текст: <code>.cbase64 текст</code>")
        return

    encoded = encode_text(value)
    if not fits_message(encoded):
        await msg.edit("Результат слишком длинный для сообщения Telegram.")
        return

    await msg.edit(
        "<b>Base64:</b>\n"
        f"<code>{html.escape(encoded)}</code>"
    )


@Client.on_message(filters.command("dbase64", prefixes=PREFIXES) & ONLY_ME)
async def decode_base64_handler(_, msg: Message):
    value = extract_argument(msg)
    if not value:
        await msg.edit("Укажите строку: <code>.dbase64 SGVsbG8=</code>")
        return

    try:
        decoded = decode_text(value)
    except ValueError:
        await msg.edit("Строка не является корректным Base64-текстом.")
        return

    if not fits_message(decoded):
        await msg.edit("Результат слишком длинный для сообщения Telegram.")
        return

    await msg.edit(f"<b>Текст:</b>\n<code>{html.escape(decoded)}</code>")
