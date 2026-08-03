import os
import io
import random
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InputMediaPhoto
from utils import ONLY_ME, link_emoji, tt_emoji

@Client.on_message(filters.command("tt", prefixes=".") & ONLY_ME)
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

        if images:
            count = len(images)
            await msg.edit(f"📸 <b>Нашел слайд-шоу ({count} фото). Качаю...</b>")
            media_group = []

            for i, img_url in enumerate(images):
                img_bytes = requests.get(img_url).content
                photo_io = io.BytesIO(img_bytes)
                photo_io.name = f"image_{i}.jpg"
                caption = f'📸 <b>{title}</b>\n<emoji id="{link_emoji}">🔗</emoji> <a href="{url}">Оригинал</a>' if i == 0 else ""
                media_group.append(InputMediaPhoto(photo_io, caption=caption))

            await msg.edit("📤 <b>Загружаю альбом...</b>")
            chunk_size = 10
            thread_id = getattr(msg, "message_thread_id", None)
            for i in range(0, len(media_group), chunk_size):
                chunk = media_group[i:i + chunk_size]
                await client.send_media_group(chat_id=msg.chat.id, media=chunk, message_thread_id=thread_id)
            await msg.delete()
            return

        play_url = video_data.get("play")
        if not play_url:
            await msg.edit("❌ Ссылка на видео не найдена.")
            return

        if not play_url.startswith("http"):
            play_url = "https://www.tikwm.com" + play_url

        await msg.edit("📥 <b>Качаю видео...</b>")
        video_bytes = requests.get(play_url).content
        file_name = f"tt_{random.randint(1000, 9999)}.mp4"
        with open(file_name, "wb") as f:
            f.write(video_bytes)

        await msg.edit("📤 <b>Загружаю видео...</b>")
        thread_id = getattr(msg, "message_thread_id", None)
        await client.send_video(
            chat_id=msg.chat.id,
            video=file_name,
            caption=f'<emoji id="{tt_emoji}">🎥</emoji> <b>{title}</b>\n<emoji id="{link_emoji}">🔗</emoji> <a href="{url}">Оригинал</a>',
            message_thread_id=thread_id
        )
        await msg.delete()

    except Exception as e:
        await msg.edit(f"❌ Ошибка: {e}")
    finally:
        if file_name and os.path.exists(file_name):
            os.remove(file_name)
