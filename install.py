import os
import sys

if not os.path.exists("config.py"):
    print("❌ Файл config.py не найден!")
    print("Пожалуйста, скопируйте config.example.py в config.py и заполните свои данные (API_ID, API_HASH).")
    print("После этого снова запустите этот скрипт.")
    sys.exit(1)

try:
    import config
    from pyrogram import Client
except ImportError:
    print("❌ Библиотека Pyrogram не установлена.")
    print("Установите зависимости командой: pip install -r requirements.txt")
    sys.exit(1)

if not hasattr(config, "api_id") or not hasattr(config, "api_hash"):
    print("❌ В config.py отсутствуют api_id или api_hash!")
    sys.exit(1)

print("Начинаем авторизацию в Telegram и создание файла сессии...")
print("Следуйте инструкциям на экране (нужно будет ввести номер телефона и код подтверждения из Telegram).")
print("-" * 50)

app = Client(
    "my_userbot",
    api_id=config.api_id,
    api_hash=config.api_hash,
    device_model="Firefox 140",
    app_version="2.2 K (Modular)",
    lang_code="en"
)

try:
    app.start()
    print("\n" + "-" * 50)
    print("✅ Сессия успешно создана! Файл 'my_userbot.session' сохранён в папке проекта.")
    print("Теперь вы можете запустить юзербота командой:")
    print("python main.py")
    app.stop()
except Exception as e:
    print(f"\n❌ Возникла ошибка при создании сессии: {e}")
