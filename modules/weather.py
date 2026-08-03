import requests
import pytz
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import ONLY_ME, DEFAULT_CITY, loading_effect, get_weather_emoji, world_emoji, clock_emoji, temp_emoji, calendar_emoji

@Client.on_message(filters.command("weather", prefixes=".") & ONLY_ME)
async def weather_handler(_, msg: Message):
    city = DEFAULT_CITY
    if len(msg.command) > 1:
        city = msg.text.split(maxsplit=1)[1]

    await loading_effect(msg, f"Ищу {city}", f'<emoji id="{world_emoji}">🌍</emoji>')

    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=ru&format=json"
        geo_r = requests.get(geo_url).json()

        if not geo_r.get('results'):
            await msg.edit(f"❌ Город <b>{city}</b> не найден.")
            return

        r = geo_r['results'][0]
        lat, lon = r['latitude'], r['longitude']
        city_name = r['name']

        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,weathercode&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=auto"
        w_r = requests.get(w_url).json()

        tz_str = w_r.get('timezone', 'UTC')
        local_now = datetime.now(pytz.timezone(tz_str))
        current_hour = local_now.hour
        time_str = local_now.strftime("%H:%M")

        text = f'<emoji id="{world_emoji}">🌍</emoji> <b>{city_name}</b> \n<emoji id="{clock_emoji}">🕒</emoji> Местное: <b>{time_str}</b>\n\n'
        text += f'<emoji id="{temp_emoji}">🌡</emoji> <b>Прогноз:</b>\n'
        
        h_temps = w_r['hourly']['temperature_2m']
        h_codes = w_r['hourly']['weathercode']

        for i in range(4):
            idx = current_hour + i
            if idx >= len(h_temps): break
            emoji = get_weather_emoji(h_codes[idx])
            disp_h = idx % 24
            text += f"<code>{disp_h:02}:00</code> {emoji} <b>{h_temps[idx]}°</b>\n"

        text += f'\n<emoji id="{calendar_emoji}">📅</emoji> <b>Неделя:</b>\n'
        d_max = w_r['daily']['temperature_2m_max']
        d_min = w_r['daily']['temperature_2m_min']
        d_codes = w_r['daily']['weathercode']
        dates = w_r['daily']['time']

        for i in range(7):
            dt = datetime.strptime(dates[i], "%Y-%m-%d").strftime("%d.%m")
            emoji = get_weather_emoji(d_codes[i])
            text += f"<code>{dt}</code>: {emoji} {round(d_min[i])}°..{round(d_max[i])}°\n"

        await msg.edit(text)

    except Exception as e:
        await msg.edit(f"❌ Ошибка: {e}")
