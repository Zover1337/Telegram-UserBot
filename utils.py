import os
import io
import asyncio
import base64
import requests
from pyrogram import filters
from pyrogram.types import Message
import config

# --- 🛠 Патч для бага Pyrofork 2.3.69 (missing 'topics' в Messages.__init__) ---
try:
    import inspect
    import functools
    from pyrogram import raw
    for _cls_name in ("Messages", "MessagesSlice", "ChannelMessages"):
        if hasattr(raw.types.messages, _cls_name):
            _cls = getattr(raw.types.messages, _cls_name)
            _orig_init = _cls.__init__
            _params = inspect.signature(_orig_init).parameters
            if "topics" in _params and _params["topics"].default is inspect.Parameter.empty:
                def _make_patched_init(orig_init):
                    @functools.wraps(orig_init)
                    def _patched_init(self, *args, **kwargs):
                        if "topics" not in kwargs:
                            kwargs["topics"] = []
                        return orig_init(self, *args, **kwargs)
                    return _patched_init
                _cls.__init__ = _make_patched_init(_orig_init)
except Exception:
    pass

# --- ⚙️ КОНФИГ ---
api_id = config.api_id
api_hash = config.api_hash

spotify_client_id = config.SPOTIFY_CLIENT_ID
spotify_client_secret = config.SPOTIFY_CLIENT_SECRET
spotify_refresh_token = config.SPOTIFY_REFRESH_TOKEN

DEFAULT_CITY = config.DEFAULT_CITY

# Emojies
ton_emoji = "5424912684078348533"
usa_emoji = "5202021044105257611"
internet_emoji = "5447410659077661506"
spotify_emoji = "5935973449674527211"
temp_emoji = "5470049770997292425"
calendar_emoji = "5967412305338568701"
clock_emoji = "5778605968208170641"
world_emoji = "5399898266265475100"
usd_emoji = "5116648080787112958"
up_emoji = "5244837092042750681"
down_emoji = "5246762912428603768"
redc_emoji = "5262479812672377939"
greenc_emoji = "5265060538261461235"
cross_emoji = "5334878195185367136"
check_emoji = "5123163417326126159"
rocket_emoji = "5445284980978621387"
link_emoji = "5877465816030515018"
black_emoji = "5411091492204716695"
attention_emoji = "5274099962655816924"
sbp_emoji = "5305413839066525446"
sber_emoji = "5301244718607264131"
tbank_emoji = "5300890611438610103"
zamok_emoji = "5296369303661067030"
tt_emoji = "5895712202903522988"

ONLY_ME = filters.me

# --- 🛠 ХЕЛПЕРЫ ---
async def spotify_get_access_token():
    url = "https://accounts.spotify.com/api/token"
    auth_str = f"{spotify_client_id}:{spotify_client_secret}"
    headers = {
        "Authorization": "Basic " + base64.b64encode(auth_str.encode()).decode()
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": spotify_refresh_token
    }
    r = requests.post(url, headers=headers, data=data).json()
    return r.get("access_token")

async def loading_effect(msg: Message, text="Загрузка", icon="⏳"):
    try:
        await msg.edit(f"{icon} {text}")
        await asyncio.sleep(0.2)
        await msg.edit(f"{icon} {text}.")
        await asyncio.sleep(0.2)
        await msg.edit(f"{icon} {text}..")
    except:
        pass

def get_weather_emoji(code):
    if code == 0: return "☀️"
    if code in [1, 2, 3]: return "⛅️"
    if code in [45, 48]: return "🌫"
    if code in [51, 53, 55, 61, 63, 65]: return "🌧"
    if code in [71, 73, 75, 77]: return "❄️"
    if code in [80, 81, 82]: return "🌦"
    if code in [95, 96, 99]: return "⛈"
    return "🌡"
