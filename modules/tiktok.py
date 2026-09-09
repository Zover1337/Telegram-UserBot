__MODULE__ = "TikTok 🎥"
__HELP__ = "<code>.tt &lt;link&gt;</code> — Скачать TikTok видео/слайды"

import os
import io
import math
import asyncio
import random
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InputMediaPhoto
from utils import ONLY_ME, PREFIXES, link_emoji, tt_emoji

@Client.on_message(filters.command("tt", prefixes=PREFIXES) & ONLY_ME)
async def tt_handler(client: Client, msg: Message):
    file_name = None
    url = None

    if len(msg.command) > 1:
        url = msg.text.split(maxsplit=1)[1]
    elif msg.reply_to_message:
        url = msg.reply_to_message.text or msg.reply_to_message.caption

    if not url or "tiktok.com" not in url:
        await msg.edit("❌ Нужна ссылка на TikTok.")
        return

    await msg.edit("🔎 <b>Ищу контент...</b>")

    try:
        api_url = "https://www.tikwm.com/api/"
        data = {"url": url, "count": 12, "cursor": 0, "web": 1, "hd": 1}
        resp = requests.post(api_url, data=data).json()

        if resp.get("code") != 0:
            await msg.edit(f"❌ Ошибка API: {resp.get('msg')}")
            return

        video_data = resp.get("data", {})
        title = video_data.get("title", "TikTok Content")[:100]
        images = video_data.get("images")

        send_kwargs = {}
        thread_id = getattr(msg, "message_thread_id", None)
        if thread_id:
            send_kwargs["message_thread_id"] = thread_id

        if images:
            count = len(images)
            await msg.edit(f"📸 <b>Нашел слайд-шоу ({count} фото). Качаю...</b>")
            
            chunk_size = 10
            total_chunks = math.ceil(count / chunk_size)
            
            # Скачиваем все фото в память
            photos_data = []
            for i, img_url in enumerate(images):
                img_bytes = requests.get(img_url, timeout=20).content
                photo_io = io.BytesIO(img_bytes)
                photo_io.name = f"image_{i}.jpg"
                photos_data.append(photo_io)

            await msg.edit("📤 <b>Загружаю альбом...</b>")

            for chunk_idx, i in enumerate(range(0, count, chunk_size)):
                chunk_photos = photos_data[i:i + chunk_size]
                part_info = f" ({chunk_idx + 1}/{total_chunks})" if total_chunks > 1 else ""
                caption = f'📸 <b>{title}</b>{part_info}\n<emoji id="{link_emoji}">🔗</emoji> <a href="{url}">Оригинал</a>'
                
                chunk_media = []
                for j, photo in enumerate(chunk_photos):
                    photo.seek(0)
                    chunk_media.append(InputMediaPhoto(photo, caption=caption if j == 0 else ""))

                try:
                    if len(chunk_media) > 1:
                        await client.send_media_group(chat_id=msg.chat.id, media=chunk_media, **send_kwargs)
                    else:
                        chunk_photos[0].seek(0)
                        await client.send_photo(
                            chat_id=msg.chat.id,
                            photo=chunk_photos[0],
                            caption=caption,
                            **send_kwargs
                        )
                except TypeError as e:
                    if "topics" in str(e):
                        # Известный баг Pyrofork 2.3.69: медиа уже отправлено в Telegram,
                        # но библиотека падает при разборе ответа сервера из-за topics
                        pass
                    else:
                        raise

                if chunk_idx + 1 < total_chunks:
                    await asyncio.sleep(0.5)

            await msg.delete()
            return

        play_url = video_data.get("play")
        if not play_url:
            await msg.edit("❌ Ссылка на видео не найдена.")
            return

        if not play_url.startswith("http"):
            play_url = "https://www.tikwm.com" + play_url

        await msg.edit("📥 <b>Качаю видео...</b>")
        video_bytes = requests.get(play_url, timeout=30).content
        file_name = f"tt_{random.randint(1000, 9999)}.mp4"
        with open(file_name, "wb") as f:
            f.write(video_bytes)

        await msg.edit("📤 <b>Загружаю видео...</b>")
        await client.send_video(
            chat_id=msg.chat.id,
            video=file_name,
            caption=f'<emoji id="{tt_emoji}">🎥</emoji> <b>{title}</b>\n<emoji id="{link_emoji}">🔗</emoji> <a href="{url}">Оригинал</a>',
            **send_kwargs
        )
        await msg.delete()

    except Exception as e:
        await msg.edit(f"❌ Ошибка: {e}")
    finally:
        if file_name and os.path.exists(file_name):
            os.remove(file_name)
