import os
import sys
import getpass

if not os.path.exists("config.py"):
    print("❌ Файл config.py не найден!")
    print("Пожалуйста, скопируйте config.example.py в config.py и заполните свои данные (API_ID, API_HASH).")
    print("После этого снова запустите этот скрипт.")
    sys.exit(1)

try:
    import config
    from pyrogram import Client
    import aiohttp
except ImportError:
    print("❌ Не установлены необходимые библиотеки (Pyrofork, aiohttp и др.).")
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

def generate_systemd_service():
    print("\n" + "-" * 50)
    ans = input("⚙️ Хотите сгенерировать systemd сервис для работы бота 24/7 (актуально для серверов Linux)? (y/n): ").strip().lower()
    if ans != 'y' and ans != 'н': # 'н' если раскладка русская
        return
        
    cwd = os.getcwd()
    user = getpass.getuser()
    python_exec = sys.executable
    
    service_content = f"""[Unit]
Description=Telegram Modular Userbot
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={cwd}
ExecStart={python_exec} {os.path.join(cwd, 'main.py')}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    
    service_path = "userbot.service"
    with open(service_path, "w", encoding="utf-8") as f:
        f.write(service_content)
        
    print(f"\n✅ Файл сервиса сгенерирован: {service_path}")
    print("\nЧтобы установить и запустить его в системе, выполните следующие команды:")
    print(f"sudo cp {service_path} /etc/systemd/system/userbot.service")
    print("sudo systemctl daemon-reload")
    print("sudo systemctl enable userbot.service")
    print("sudo systemctl start userbot.service")
    print("\nПроверить логи/статус: sudo systemctl status userbot.service")

try:
    app.start()
    print("\n" + "-" * 50)
    print("✅ Сессия успешно создана! Файл 'my_userbot.session' сохранён в папке проекта.")
    print("Вы можете запустить юзербота вручную командой: python main.py")
    app.stop()
    
    generate_systemd_service()
    
except Exception as e:
    print(f"\n❌ Возникла ошибка при создании сессии: {e}")
