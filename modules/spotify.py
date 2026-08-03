import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import ONLY_ME, spotify_get_access_token, link_emoji, spotify_emoji

@Client.on_message(filters.command("spotify", prefixes=".") & ONLY_ME)
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

        await msg.edit(f'<emoji id="{link_emoji}">🔗</emoji> <i>Ищу ссылки на других платформах...</i>')
        songlink_url = f"https://api.song.link/v1-alpha.1/links?url={spotify_url}"
        try:
            sl_response = requests.get(songlink_url, timeout=20)
            sl_response.raise_for_status()
            sl_data = sl_response.json()
        except Exception as e:
            sl_data = None
            print(f"Song.link error: {e}")

        caption = f'<emoji id="{spotify_emoji}">🎧</emoji> <b>Сейчас играет:</b>\n<b>{artists} — {name}</b>\n\n<emoji id="{link_emoji}">🔗</emoji> <b>Spotify:</b> <a href="{spotify_url}">слушать</a>'

        if sl_data and "linksByPlatform" in sl_data:
            platforms = {
                "appleMusic": (f'<emoji id="{link_emoji}">🔗</emoji> <b>Apple Music</b>', "appleMusic"),
                "soundcloud": (f'<emoji id="{link_emoji}">🔗</emoji> <b>SoundCloud</b>', "soundcloud"),
                "yandex": (f'<emoji id="{link_emoji}">🔗</emoji> <b>Яндекс Музыка</b>', "yandex"),
                "youtubeMusic": (f'<emoji id="{link_emoji}">🔗</emoji> <b>YouTube Music</b>', "youtubeMusic"),
            }
            added = False
            for key, (label, platform_key) in platforms.items():
                platform_info = sl_data["linksByPlatform"].get(platform_key)
                if platform_info and "url" in platform_info:
                    caption += f'\n{label}: <a href="{platform_info["url"]}">слушать</a>'
                    added = True
            if not added:
                caption += "\n\n<i>Другие платформы не найдены</i>"
        else:
            caption += "\n\nНе удалось получить ссылки на другие платформы"

        thumbnail_url = None
        if sl_data and "entitiesByUniqueId" in sl_data:
            spotify_entity_id = None
            if "linksByPlatform" in sl_data and "spotify" in sl_data["linksByPlatform"]:
                spotify_entity_id = sl_data["linksByPlatform"]["spotify"].get("entityUniqueId")
            if spotify_entity_id and spotify_entity_id in sl_data["entitiesByUniqueId"]:
                thumbnail_url = sl_data["entitiesByUniqueId"][spotify_entity_id].get("thumbnailUrl")
            if not thumbnail_url:
                for entity in sl_data["entitiesByUniqueId"].values():
                    if entity.get("thumbnailUrl"):
                        thumbnail_url = entity["thumbnailUrl"]
                        break

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
