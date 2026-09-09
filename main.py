import config
import utils
from pyrogram import Client
from pyrogram.enums import ParseMode

# --- ⚙️ КОНФИГ ---
api_id = config.api_id
api_hash = config.api_hash

# Инициализация клиента (добавлен глобальный ParseMode.HTML)
# Указываем папку 'modules' для автоматической загрузки плагинов
app = Client(
    "my_userbot", 
    api_id=api_id, 
    api_hash=api_hash, 
    device_model="Firefox 140",
    app_version="2.2 K (Modular)",
    lang_code="en",
    parse_mode=ParseMode.HTML,
    plugins=dict(root="modules")
)

if __name__ == "__main__":
    print("🔒 Юзербот запущен в модульном режиме. Модули загружены из папки 'modules/'.")
    print("Реагирует только на тебя.")
    app.run()