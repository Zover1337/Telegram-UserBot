__MODULE__ = "Информация об IP 🌐"
__HELP__ = "<code>.ipi &lt;IP&gt;</code> — Показать данные IPv4 или IPv6"

import html
import ipaddress

from pyrogram import Client, filters
from pyrogram.types import Message

from utils import ONLY_ME, PREFIXES


def normalize_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError as exc:
        raise ValueError("Некорректный IP-адрес") from exc


def _safe(value, default="Нет данных") -> str:
    if value is None or value == "":
        value = default
    return html.escape(str(value))


def _nested_object(data: dict, key: str) -> dict:
    if key not in data:
        return {}
    value = data[key]
    if not isinstance(value, dict):
        raise ValueError("Invalid IP API response")
    return value


def format_ip_info(data: dict) -> str:
    if not isinstance(data, dict):
        raise ValueError("Invalid IP API response")
    connection = _nested_object(data, "connection")
    currency = _nested_object(data, "currency")
    timezone = _nested_object(data, "timezone")
    country_code = _safe(data.get("country_code"), "--")
    location = f"{_safe(data.get('latitude'))}, {_safe(data.get('longitude'))}"

    return (
        "<b>Информация об IP</b>\n\n"
        f"IP: <code>{_safe(data.get('ip'))}</code>\n"
        f"Регион: <code>{_safe(data.get('region'))}</code>\n"
        f"Город: <code>{_safe(data.get('city'))}</code>\n"
        f"Страна: <code>{_safe(data.get('country'))} ({country_code})</code>\n"
        f"Континент: <code>{_safe(data.get('continent'))}</code>\n"
        f"Почтовый индекс: <code>{_safe(data.get('postal'))}</code>\n"
        f"Организация: <code>{_safe(connection.get('org'))}</code>\n"
        f"Валюта: <code>{_safe(currency.get('code'))} ({_safe(currency.get('symbol'))})</code>\n"
        f"Координаты: <code>{location}</code>\n"
        f"Часовой пояс: <code>{_safe(timezone.get('id'))}</code>"
    )


@Client.on_message(filters.command("ipi", prefixes=PREFIXES) & ONLY_ME)
async def info_ip_handler(_, msg: Message):
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await msg.edit("Укажите адрес: <code>.ipi 1.1.1.1</code>")
        return

    try:
        ip = normalize_ip(parts[1])
    except ValueError:
        await msg.edit("Некорректный IPv4 или IPv6 адрес.")
        return

    await msg.edit(f"Получаю данные для <code>{html.escape(ip)}</code>...")

    try:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"https://ipwho.is/{ip}") as response:
                if response.status != 200:
                    await msg.edit(f"Сервис IP-данных вернул HTTP {response.status}.")
                    return
                data = await response.json(content_type=None)
    except Exception:
        await msg.edit("Не удалось получить данные об IP. Повторите позже.")
        return

    if not isinstance(data, dict):
        await msg.edit("Сервис IP-данных вернул некорректный ответ.")
        return
    if not data.get("success", True):
        await msg.edit("Сервис не нашёл данные для этого IP.")
        return

    try:
        text = format_ip_info(data)
    except ValueError:
        await msg.edit("Сервис IP-данных вернул некорректный ответ.")
        return
    await msg.edit(text)
