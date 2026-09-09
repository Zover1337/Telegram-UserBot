__MODULE__ = "Check-Host 🌐"
__HELP__ = (
    "<code>.ping &lt;хост&gt;</code> — Проверка пинга по странам\n"
    "<code>.tcp &lt;хост:порт&gt;</code> — Проверка TCP порта\n"
    "<code>.udp &lt;хост:порт&gt;</code> — Проверка UDP порта\n"
    "<code>.http &lt;url/хост&gt;</code> — Проверка HTTP/HTTPS ответа\n"
    "<code>.dns &lt;домен&gt;</code> — Проверка DNS резолва"
)

import asyncio
import re
from urllib.parse import urlparse
from collections import Counter
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified
from utils import ONLY_ME, internet_emoji, world_emoji, link_emoji, check_emoji, cross_emoji

# --- 🌍 СЛОВАРИ СТРАН И ГОРОДОВ CHECK-HOST ---
COUNTRY_RU = {
    "us": "США", "ru": "Россия", "de": "Германия", "ua": "Украина", "kz": "Казахстан",
    "by": "Беларусь", "fr": "Франция", "gb": "Великобритания", "uk": "Великобритания",
    "nl": "Нидерланды", "pl": "Польша", "it": "Италия", "es": "Испания", "tr": "Турция",
    "ch": "Швейцария", "se": "Швеция", "fi": "Финляндия", "sg": "Сингапур", "jp": "Япония",
    "hk": "Гонконг", "in": "Индия", "br": "Бразилия", "ca": "Канада", "il": "Израиль",
    "id": "Индонезия", "ir": "Иран", "at": "Австрия", "bg": "Болгария", "cy": "Кипр",
    "cz": "Чехия", "ee": "Эстония", "ge": "Грузия", "gr": "Греция", "hu": "Венгрия",
    "md": "Молдова", "no": "Норвегия", "ro": "Румыния", "rs": "Сербия", "si": "Словения",
    "sk": "Словакия", "vn": "Вьетнам", "ae": "ОАЭ", "au": "Австралия"
}

CITY_RU = {
    "Moscow": "Москва", "Saint Petersburg": "Санкт-Петербург", "Kyiv": "Киев",
    "Khmelnytskyi": "Хмельницкий", "Karaganda": "Караганда", "Almaty": "Алматы",
    "Minsk": "Минск", "Frankfurt": "Франкфурт", "Nuremberg": "Нюрнберг",
    "Langen": "Ланген", "Falkenstein": "Фалькенштайн", "Paris": "Париж",
    "London": "Лондон", "Amsterdam": "Амстердам", "Meppel": "Меппел",
    "Warsaw": "Варшава", "Milan": "Милан", "Rome": "Рим", "Madrid": "Мадрид",
    "Barcelona": "Барселона", "Istanbul": "Стамбул", "Zurich": "Цюрих",
    "Stockholm": "Стокгольм", "Helsinki": "Хельсинки", "Singapore": "Сингапур",
    "Tokyo": "Токио", "Hong Kong": "Гонконг", "Mumbai": "Мумбаи",
    "Sao Paulo": "Сан-Паулу", "Toronto": "Торонто", "Vancouver": "Ванкувер",
    "Tel Aviv": "Тель-Авив", "Netanya": "Нетания", "Jakarta": "Джакарта",
    "Tehran": "Тегеран", "Isfahan": "Исфахан", "Shiraz": "Шираз",
    "Vienna": "Вена", "Sofia": "София", "Larnaca": "Ларнака",
    "Prague": "Прага", "Tallinn": "Таллин", "Tbilisi": "Тбилиси",
    "Athens": "Афины", "Budapest": "Будапешт", "Chisinau": "Кишинёв",
    "Oslo": "Осло", "Bucharest": "Бухарест", "Belgrade": "Белград",
    "Maribor": "Марибор", "Bratislava": "Братислава", "Ho Chi Minh City": "Хошимин",
    "Dubai": "Дубай", "Sydney": "Сидней", "Los Angeles": "Лос-Анджелес",
    "Dallas": "Даллас", "Atlanta": "Атланта", "Miami": "Майами",
    "New York": "Нью-Йорк", "Chicago": "Чикаго", "Seattle": "Сиэтл"
}

# --- ✨ ВСПОМОГАТЕЛЬНЫЙ КЛАСС ЭМОДЗИ ---
class EmojiHelper:
    def __init__(self, client: Client):
        me = getattr(client, "me", None)
        self.is_prem = bool(getattr(me, "is_premium", False))

    def tag(self, eid: str, fallback: str) -> str:
        if self.is_prem:
            return f'<emoji id="{eid}">{fallback}</emoji>'
        return fallback

    @property
    def cross(self) -> str:
        return self.tag(cross_emoji, "❌")

    @property
    def check(self) -> str:
        return self.tag(check_emoji, "✅")

    @property
    def planet(self) -> str:
        return self.tag(world_emoji, "🌍")

    @property
    def globe(self) -> str:
        return self.tag(internet_emoji, "🌐")

    @property
    def link(self) -> str:
        return self.tag(link_emoji, "🔗")


def get_flag_emoji(code: str) -> str:
    """Генерация флага страны по двухбуквенному коду ISO."""
    if not code or len(code) != 2 or not code.isalpha():
        return "🌐"
    return "".join(chr(127397 + ord(c)) for c in code.upper())


def sanitize_target(check_type: str, raw_target: str) -> str:
    """Нормализация цели под конкретный тип проверки Check-Host."""
    target = raw_target.strip()

    if check_type in ("ping", "dns"):
        if "://" in target:
            parsed = urlparse(target)
            target = parsed.hostname or parsed.netloc or parsed.path
        if ":" in target and not target.startswith("["):
            target = target.split(":")[0]
        target = target.split("/")[0]
        return target.strip()

    elif check_type in ("tcp", "udp"):
        if "://" in target:
            parsed = urlparse(target)
            host = parsed.hostname or parsed.netloc
            port = parsed.port
            target = f"{host}:{port}" if port else host
        target = target.split("/")[0]
        return target.strip()

    elif check_type == "http":
        return target.strip()

    return target.strip()


def format_node_result(check_type: str, res, em: EmojiHelper) -> str:
    """Форматирование результата ответа отдельной ноды Check-Host."""
    if res is None:
        return "⏳"

    check_icon = em.check
    cross_icon = em.cross

    if check_type == "ping":
        # res: [[["OK", time_sec, ip], ...]] или [[null]] или [null]
        if not res or not isinstance(res, list) or not res[0] or res[0][0] is None:
            return f"{cross_icon} <b>Не найден / DNS</b>"
        attempts = res[0]
        ok_pings = [p[1] for p in attempts if isinstance(p, list) and len(p) > 1 and p[0] == "OK"]
        total = len(attempts)
        received = len(ok_pings)

        if received == total and total > 0:
            avg_ms = (sum(ok_pings) / received) * 1000
            ms_str = f"{avg_ms:.1f}" if avg_ms < 10 else f"{int(round(avg_ms))}"
            return f"{check_icon} <b>{ms_str} ms</b>"
        elif received > 0:
            avg_ms = (sum(ok_pings) / received) * 1000
            ms_str = f"{avg_ms:.1f}" if avg_ms < 10 else f"{int(round(avg_ms))}"
            return f"⚠️ <b>{ms_str} ms</b> ({received}/{total})"
        else:
            return f"{cross_icon} <b>Таймаут (0/{total})</b>"

    elif check_type == "tcp":
        # res: [{"address": "...", "time": 0.01}] или [{"error": "Connection timed out"}]
        if not res or not isinstance(res, list) or not res[0]:
            return f"{cross_icon} <b>Ошибка</b>"
        item = res[0]
        if "error" in item:
            err = str(item["error"])
            if "timed out" in err.lower():
                err_text = "Таймаут"
            elif "refused" in err.lower():
                err_text = "Сброшено"
            else:
                err_text = err
            return f"{cross_icon} <b>{err_text}</b>"
        time_ms = item.get("time", 0) * 1000
        ms_str = f"{time_ms:.1f}" if time_ms < 10 else f"{int(round(time_ms))}"
        return f"{check_icon} <b>{ms_str} ms</b>"

    elif check_type == "udp":
        # res: [{"address": "...", "timeout": 1}] или [{"error": "..."}]
        if not res or not isinstance(res, list) or not res[0]:
            return f"{cross_icon} <b>Ошибка</b>"
        item = res[0]
        if "error" in item:
            return f"{cross_icon} <b>{item['error']}</b>"
        return f"{check_icon} <b>Открыт / фильтр</b>"

    elif check_type == "http":
        # res: [[ok_flag, time_sec, msg, code_str, ip]]
        if not res or not isinstance(res, list) or not res[0]:
            return f"{cross_icon} <b>Ошибка</b>"
        item = res[0]
        ok_flag = item[0]
        time_ms = item[1] * 1000 if len(item) > 1 and item[1] else 0
        msg_str = item[2] if len(item) > 2 and item[2] else ""
        code_str = str(item[3]) if len(item) > 3 and item[3] else ""
        ms_str = f"{int(round(time_ms))} ms"

        if ok_flag:
            label = f"{code_str} {msg_str}".strip() or "OK"
            return f"{check_icon} <b>{label} ({ms_str})</b>"
        else:
            err_label = f"{code_str} {msg_str}".strip() or "Ошибка"
            return f"{cross_icon} <b>{err_label}</b>"

    elif check_type == "dns":
        # res: [{"A": [...], "AAAA": [...], "TTL": ...}]
        if not res or not isinstance(res, list) or not res[0]:
            return f"{cross_icon} <b>Ошибка</b>"
        item = res[0]
        records = []
        for k in ("A", "AAAA"):
            if k in item and isinstance(item[k], list):
                records.extend(item[k])
        if records:
            ips = ", ".join(records[:2])
            ttl = f" (TTL {item['TTL']})" if item.get("TTL") else ""
            return f"{check_icon} <code>{ips}</code>{ttl}"
        return f"{cross_icon} <b>Не найден</b>"

    return "—"


def build_message(
    check_type: str,
    target: str,
    node_list: list,
    results: dict,
    perm_link: str,
    done_count: int,
    total_count: int,
    em: EmojiHelper,
    is_finished: bool = False
) -> str:
    """Сборка HTML-сообщения со статусом, списком нод и ссылкой на Check-Host."""
    type_names = {
        "ping": "PING",
        "tcp": "TCP",
        "udp": "UDP",
        "http": "HTTP",
        "dns": "DNS"
    }
    type_title = type_names.get(check_type, check_type.upper())

    if is_finished:
        status_line = f"{em.planet} <i>Проверка завершена ({done_count}/{total_count})</i>"
    else:
        status_line = f"{em.planet} <i>Проверка узлов... ({done_count}/{total_count})</i>"

    header = (
        f"{em.globe} <b>Check-Host</b> • <b>{type_title}</b>: <code>{target}</code>\n"
        f"{status_line}\n\n"
    )
    footer = f"\n{em.link} <a href=\"{perm_link}\">Полный отчёт на Check-Host</a>"

    # Формируем строки стран
    body_lines = []
    omitted = 0
    for item in node_list:
        node_id = item["node_id"]
        loc_str = item["loc_str"]
        res = results.get(node_id)
        res_str = format_node_result(check_type, res, em)
        line = f"{loc_str}: {res_str}"

        # Защита от лимита 4096 символов Telegram (по чистому тексту без HTML-тегов)
        test_text = header + "\n".join(body_lines + [line]) + footer
        clean_len = len(re.sub(r"<[^>]+>", "", test_text))
        if clean_len > 4000:
            omitted = len(node_list) - len(body_lines)
            break
        body_lines.append(line)

    if omitted > 0:
        body_lines.append(f"<i>...и ещё {omitted} узлов (см. ссылку)</i>")

    return header + "\n".join(body_lines) + footer


async def execute_check(
    client: Client,
    msg: Message,
    check_type: str,
    target: str,
    max_nodes: int = None
):
    """Основной воркер выполнения проверки с плавным редактированием сообщения."""
    em = EmojiHelper(client)
    clean_target = sanitize_target(check_type, target)

    if not clean_target:
        await msg.edit(f"{em.cross} Не удалось распознать цель для проверки.")
        return

    type_title = check_type.upper()
    await msg.edit(
        f"{em.globe} <b>Check-Host</b> • <b>{type_title}</b>: <code>{clean_target}</code>\n"
        f"{em.planet} <i>Инициализация проверки...</i>"
    )

    headers = {"Accept": "application/json"}
    init_url = f"https://check-host.net/check-{check_type}?host={clean_target}"
    if max_nodes:
        init_url += f"&max_nodes={max_nodes}"

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(init_url, headers=headers) as resp:
                if resp.status != 200:
                    await msg.edit(f"{em.cross} Check-Host вернул ошибку HTTP {resp.status}")
                    return
                data = await resp.json()

            if not data.get("ok"):
                err_msg = data.get("error") or "Неизвестная ошибка инициализации"
                await msg.edit(f"{em.cross} Check-Host: {err_msg}")
                return

            req_id = data.get("request_id")
            perm_link = data.get("permanent_link", f"https://check-host.net/check-report/{req_id}")
            nodes_raw = data.get("nodes", {})

            if not nodes_raw:
                await msg.edit(f"{em.cross} Check-Host не вернул узлов для проверки.")
                return

            # Подсчёт встречаемости стран для определения дубликатов
            country_names = []
            for node_id, ninfo in nodes_raw.items():
                code = ninfo[0] if len(ninfo) > 0 else ""
                c_en = ninfo[1] if len(ninfo) > 1 else ""
                c_ru = COUNTRY_RU.get(code.lower(), COUNTRY_RU.get(c_en.lower(), c_en))
                country_names.append(c_ru)

            country_counts = Counter(country_names)

            # Формируем подготовленный список нод с правильным форматированием (Флаг + Страна (+ Город))
            prepared_nodes = []
            for node_id, ninfo in nodes_raw.items():
                code = ninfo[0] if len(ninfo) > 0 else ""
                c_en = ninfo[1] if len(ninfo) > 1 else ""
                city_en = ninfo[2] if len(ninfo) > 2 else ""

                c_ru = COUNTRY_RU.get(code.lower(), COUNTRY_RU.get(c_en.lower(), c_en))
                city_ru = CITY_RU.get(city_en, city_en)
                flag = get_flag_emoji(code)

                # Правило: если страна дублируется — флаг + страна + город
                if country_counts[c_ru] > 1 and city_ru:
                    loc_str = f"{flag} {c_ru} ({city_ru})"
                else:
                    loc_str = f"{flag} {c_ru}"

                prepared_nodes.append({
                    "node_id": node_id,
                    "country": c_ru,
                    "city": city_ru,
                    "loc_str": loc_str
                })

            # Сортировка по названию страны и города
            prepared_nodes.sort(key=lambda x: (x["country"], x["city"]))
            total_nodes = len(prepared_nodes)

            # --- Цикл плавного опроса и обновления сообщения ---
            last_text = ""
            results = {}
            max_wait_seconds = 35
            check_interval = 2.5
            max_loops = int(max_wait_seconds / check_interval)

            for loop_i in range(max_loops):
                await asyncio.sleep(check_interval)

                res_url = f"https://check-host.net/check-result/{req_id}"
                try:
                    async with session.get(res_url, headers=headers) as res_resp:
                        if res_resp.status == 200:
                            results = await res_resp.json()
                except Exception:
                    pass

                done_count = sum(1 for v in results.values() if v is not None)
                is_finished = done_count >= total_nodes

                new_text = build_message(
                    check_type=check_type,
                    target=clean_target,
                    node_list=prepared_nodes,
                    results=results,
                    perm_link=perm_link,
                    done_count=done_count,
                    total_count=total_nodes,
                    em=em,
                    is_finished=is_finished
                )

                if new_text != last_text:
                    try:
                        await msg.edit(new_text, disable_web_page_preview=True)
                        last_text = new_text
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value)
                    except MessageNotModified:
                        pass
                    except Exception:
                        pass

                if is_finished:
                    break

            # Финальный апдейт при выходе по таймауту, если не всё дошло
            done_count = sum(1 for v in results.values() if v is not None)
            if done_count < total_nodes:
                final_text = build_message(
                    check_type=check_type,
                    target=clean_target,
                    node_list=prepared_nodes,
                    results=results,
                    perm_link=perm_link,
                    done_count=done_count,
                    total_count=total_nodes,
                    em=em,
                    is_finished=True
                )
                if final_text != last_text:
                    try:
                        await msg.edit(final_text, disable_web_page_preview=True)
                    except Exception:
                        pass

    except Exception as e:
        await msg.edit(f"{em.cross} Ошибка выполнения проверки: {e}")


def parse_args_and_target(command_name: str, args: list, reply_msg: Message):
    """
    Разбор аргументов команд:
    Определяет check_type, target, max_nodes.
    По умолчанию max_nodes = None (все доступные узлы).
    """
    target = None
    max_nodes = None

    cmd_map = {
        "ping": "ping", "chping": "ping",
        "tcp": "tcp", "chtcp": "tcp",
        "udp": "udp", "chudp": "udp",
        "http": "http", "chhttp": "http",
        "dns": "dns", "chdns": "dns"
    }
    check_type = cmd_map.get(command_name, "ping")

    # Проверка, есть ли число узлов или 'all' среди аргументов
    filtered_args = []
    for arg in args:
        if arg.lower() == "all":
            max_nodes = None
        elif arg.isdigit() and int(arg) > 0:
            max_nodes = min(int(arg), 100)
        else:
            filtered_args.append(arg)

    if filtered_args:
        target = filtered_args[0]

    # Если цель не указана в аргументах, ищем в тексте реплая
    if not target and reply_msg and reply_msg.text:
        words = reply_msg.text.strip().split()
        if words:
            target = words[0]

    return check_type, target, max_nodes


# --- 🚀 ХЕНДЛЕРЫ КОМАНД ---


@Client.on_message(filters.command(["chping", "ping"], prefixes=".") & ONLY_ME)
async def ch_ping_handler(client: Client, msg: Message):
    args = msg.command[1:] if len(msg.command) > 1 else []
    check_type, target, max_nodes = parse_args_and_target("ping", args, msg.reply_to_message)
    if not target:
        em = EmojiHelper(client)
        await msg.edit(f"{em.globe} Укажите цель: <code>.ping 1.1.1.1</code> или ответьте на сообщение.")
        return
    await execute_check(client, msg, "ping", target, max_nodes)


@Client.on_message(filters.command(["chtcp", "tcp"], prefixes=".") & ONLY_ME)
async def ch_tcp_handler(client: Client, msg: Message):
    args = msg.command[1:] if len(msg.command) > 1 else []
    check_type, target, max_nodes = parse_args_and_target("tcp", args, msg.reply_to_message)
    if not target:
        em = EmojiHelper(client)
        await msg.edit(f"{em.globe} Укажите цель: <code>.tcp 1.1.1.1:443</code> или ответьте на сообщение.")
        return
    await execute_check(client, msg, "tcp", target, max_nodes)


@Client.on_message(filters.command(["chudp", "udp"], prefixes=".") & ONLY_ME)
async def ch_udp_handler(client: Client, msg: Message):
    args = msg.command[1:] if len(msg.command) > 1 else []
    check_type, target, max_nodes = parse_args_and_target("udp", args, msg.reply_to_message)
    if not target:
        em = EmojiHelper(client)
        await msg.edit(f"{em.globe} Укажите цель: <code>.udp 8.8.8.8:53</code> или ответьте на сообщение.")
        return
    await execute_check(client, msg, "udp", target, max_nodes)


@Client.on_message(filters.command(["chhttp", "http"], prefixes=".") & ONLY_ME)
async def ch_http_handler(client: Client, msg: Message):
    args = msg.command[1:] if len(msg.command) > 1 else []
    check_type, target, max_nodes = parse_args_and_target("http", args, msg.reply_to_message)
    if not target:
        em = EmojiHelper(client)
        await msg.edit(f"{em.globe} Укажите цель: <code>.http https://google.com</code> или ответьте на сообщение.")
        return
    await execute_check(client, msg, "http", target, max_nodes)


@Client.on_message(filters.command(["chdns", "dns"], prefixes=".") & ONLY_ME)
async def ch_dns_handler(client: Client, msg: Message):
    args = msg.command[1:] if len(msg.command) > 1 else []
    check_type, target, max_nodes = parse_args_and_target("dns", args, msg.reply_to_message)
    if not target:
        em = EmojiHelper(client)
        await msg.edit(f"{em.globe} Укажите цель: <code>.dns google.com</code> или ответьте на сообщение.")
        return
    await execute_check(client, msg, "dns", target, max_nodes)
