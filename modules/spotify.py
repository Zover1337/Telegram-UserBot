__MODULE__ = "Spotify 🎧"
__HELP__ = "<code>.spotify</code> — Какой трек сейчас играет"

import re
import json
import urllib.parse
import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import ONLY_ME, PREFIXES, spotify_get_access_token, link_emoji, spotify_emoji

try:
    import config
    SONGLINK_API_KEY = getattr(config, "SONGLINK_API_KEY", None)
except Exception:
    SONGLINK_API_KEY = None


def get_music_links(spotify_url: str, name: str, artists: str):
    """
    Получает ссылки на другие платформы:
    1. Через официальный API Songlink (если задан ключ в config.py).
    2. Путём парсинга веб-страницы song.link (Next.js data без ключа).
    3. Apple Music через бесплатный официальный iTunes Search API.
    4. Fallback на прямой поиск (YouTube Music, Yandex, SoundCloud).
    """
    links = {}
    fallback_thumbnail = None
    encoded_query = urllib.parse.quote_plus(f"{artists} {name}")

    # 1. Если задан ключ Songlink API
    if SONGLINK_API_KEY:
        try:
            sl_url = f"https://api.song.link/v1-alpha.1/links?url={spotify_url}&key={SONGLINK_API_KEY}"
            r = requests.get(sl_url, timeout=10)
            if r.status_code == 200:
                sl_data = r.json()
                for p in ["appleMusic", "yandex", "youtubeMusic", "soundcloud"]:
                    p_info = sl_data.get("linksByPlatform", {}).get(p)
                    if p_info and "url" in p_info:
                        links[p] = p_info["url"]
                return links, None
        except Exception as e:
            print(f"Songlink API key error: {e}")

    # 2. Извлечение ссылок из веб-страницы song.link
    try:
        r = requests.get(
            f"https://song.link/{spotify_url}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=8
        )
        if r.status_code == 200:
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text)
            if match:
                data = json.loads(match.group(1))
                page_data = data.get("props", {}).get("pageProps", {}).get("pageData", {})
                for s in page_data.get("sections", []):
                    if not fallback_thumbnail and s.get("thumbnailUrl"):
                        fallback_thumbnail = s.get("thumbnailUrl")
                    for l in s.get("links", []):
                        plat = l.get("platform")
                        p_url = l.get("url")
                        if plat and p_url:
                            links[plat] = p_url
    except Exception as e:
        print(f"Song.link scrape error: {e}")

    # 3. Apple Music через iTunes Search API
    if "appleMusic" not in links:
        try:
            itunes_url = f"https://itunes.apple.com/search?term={encoded_query}&entity=song&limit=1"
            it_r = requests.get(itunes_url, timeout=5).json()
            if it_r.get("resultCount", 0) > 0:
                links["appleMusic"] = it_r["results"][0]["trackViewUrl"]
        except Exception as e:
            print(f"iTunes search error: {e}")

    # 4. Fallback-ссылки на поиск
    if "youtubeMusic" not in links:
        links["youtubeMusic"] = f"https://music.youtube.com/search?q={encoded_query}"
    if "yandex" not in links:
        links["yandex"] = f"https://music.yandex.ru/search?text={encoded_query}"
    if "soundcloud" not in links:
        links["soundcloud"] = f"https://soundcloud.com/search?q={encoded_query}"

    return links, fallback_thumbnail


@Client.on_message(filters.command("spotify", prefixes=PREFIXES) & ONLY_ME)
async def spotify_handler(client: Client, msg: Message):
    await msg.edit("🎧 <i>Получаю текущий трек...</i>")

    try:
        token = await spotify_get_access_token()
        if not token:
            await msg.edit("❌ Не получил access token.")
            return

        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get("https://api.spotify.com/v1/me/player/currently-playing", headers=headers)

        if r.status_code == 204:
            await msg.edit("⏹ Сейчас ничего не играет.")
            return

        data = r.json()
        track = data["item"]
        name = track["name"]
        artists = ", ".join(a["name"] for a in track["artists"])
        spotify_url = track["external_urls"]["spotify"]

        # Берём оригинальную обложку альбома из Spotify API
        thumbnail_url = None
        images = track.get("album", {}).get("images", [])
        if images and "url" in images[0]:
            thumbnail_url = images[0]["url"]

        await msg.edit(f'<emoji id="{link_emoji}">🔗</emoji> <i>Ищу ссылки на других платформах...</i>')

        links, fallback_thumb = get_music_links(spotify_url, name, artists)
        if not thumbnail_url and fallback_thumb:
            thumbnail_url = fallback_thumb

        caption = (
            f'<emoji id="{spotify_emoji}">🎧</emoji> <b>Сейчас играет:</b>\n'
            f'<b>{artists} — {name}</b>\n\n'
            f'<emoji id="{link_emoji}">🔗</emoji> <b>Spotify:</b> <a href="{spotify_url}">слушать</a>'
        )

        platforms = [
            ("appleMusic", "Apple Music"),
            ("yandex", "Яндекс Музыка"),
            ("youtubeMusic", "YouTube Music"),
            ("soundcloud", "SoundCloud"),
        ]

        added = False
        for platform_key, label in platforms:
            url = links.get(platform_key)
            if url:
                caption += f'\n<emoji id="{link_emoji}">🔗</emoji> <b>{label}:</b> <a href="{url}">слушать</a>'
                added = True

        if not added:
            caption += "\n\n<i>Другие платформы не найдены</i>"

        if thumbnail_url:
            thread_id = getattr(msg, "message_thread_id", None)
            await client.send_photo(
                chat_id=msg.chat.id,
                photo=thumbnail_url,
                caption=caption,
                disable_notification=True,
                message_thread_id=thread_id
            )
            await msg.delete()
        else:
            await client.edit_message_text(
                chat_id=msg.chat.id,
                message_id=msg.id,
                text=caption,
                disable_web_page_preview=True
            )

    except Exception as e:
        await msg.edit(f"❌ Ошибка Spotify: {e}")

