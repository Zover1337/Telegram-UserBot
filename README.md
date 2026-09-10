# Modular Telegram Userbot

Telegram-userbot на Python и Pyrofork. Команды хранятся в отдельных файлах `modules/*.py` и загружаются при запуске.

[Руководство по созданию модулей](MODULES_GUIDE.md)

## Риски

- Telegram может ограничить или заблокировать аккаунт за автоматизированные действия и использование стороннего клиента.
- Не публикуйте `config.py`, `*.session` и токены. Эти файлы дают доступ к аккаунту и внешним сервисам.
- `.ai` и `.aimage` работают через неофициальные провайдеры `g4f`. Провайдер получает ваш запрос и может хранить его. Не отправляйте пароли, токены, личные данные и закрытые документы.
- `g4f` объединяет сторонних провайдеров и может перестать работать после изменений на их сайтах. В проекте зафиксирована проверенная версия пакета без дополнительных extras.
- `.ipi` передаёт публичные IP сервисам RIPEstat и RDAP. При настроенных ключах также используются IPinfo и ipregistry. Доменные имена сначала разрешаются системным DNS. `.cqr` создаёт QR-код локально и ничего не отправляет QR-сервисам.

Разработчик не отвечает за блокировку аккаунта, потерю данных или последствия работы сторонних сервисов.

## Возможности

- Два префикса команд: `.` и `!`.
- Обработчики принимают только ваши сообщения через `filters.me`.
- Менеджер проверяет имя файла, помещает новый модуль в карантин и показывает SHA256 перед установкой.
- Поддерживаются ручной запуск, systemd и Docker Compose.

## Установка

Нужен Python 3.10 или новее.

```bash
git clone https://github.com/Zover1337/Telegram-UserBot
cd Telegram-UserBot
python3 -m pip install -r requirements.txt
cp config.example.py config.py
```

Заполните `api_id` и `api_hash` в `config.py`. Получить их можно на [my.telegram.org](https://my.telegram.org/apps).

Создайте Telegram-сессию:

```bash
python3 install.py
```

Скрипт предложит создать unit-файл systemd. Для обычного запуска используйте:

```bash
python3 main.py
```

## Конфигурация

Параметры погоды и AI:

```python
DEFAULT_CITY = "Moscow"
AI_MODEL = "standard"
AI_IMAGE_MODEL = "flux"
AI_ROLE = "user"
AI_STREAM_DELAY = 1.2
```

Существующий `config.py` продолжит работать без AI-параметров: модуль использует значения выше по умолчанию.

Для `AI_MODEL` доступны `standard`, `online`, `gemma-4`, `gemini-2.5-flash-lite` и `deepseek-v3.2`. Текст обрабатывает сетевой провайдер DeepAI без запуска браузера. Изображения создаёт Pollinations.

Для Spotify заполните `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` и `SPOTIFY_REFRESH_TOKEN`. `SONGLINK_API_KEY` остаётся необязательным.

Для расширенных данных `.ipi` можно задать `IPINFO_TOKEN` и `IPREGISTRY_KEY`. Локальные базы GeoLite2 подключаются через `MAXMIND_CITY_DB` и `MAXMIND_ASN_DB`; без этих параметров используются бесплатные RIPEstat и RDAP.

## Команды

| Команда | Действие |
| :--- | :--- |
| `.help` | Показать список загруженных модулей и команд. |
| `.ai <вопрос>` | Получить потоковый ответ через `g4f`. |
| `.aimage <описание>` | Создать изображение через `g4f`. |
| `.cqr <текст или ссылка>` | Создать QR-код локально. |
| `.ipi <IP или домен>` | Показать сведения о публичных IPv4/IPv6 адресах. |
| `.cbase64 <текст>` | Кодировать UTF-8 текст в Base64. |
| `.dbase64 <Base64>` | Декодировать Base64 в UTF-8 текст. |
| `.weather [город]` | Показать прогноз. Без аргумента используется `DEFAULT_CITY`. |
| `.tt <ссылка>` | Скачать видео или слайд-шоу из TikTok. |
| `.usd` / `.ton` | Показать курсы валют. |
| `.ping` / `.tcp` / `.udp` / `.http` / `.dns` | Проверить хост через Check-Host. |
| `.spotify` | Показать текущий трек Spotify и ссылки на площадки. |
| `.rand_anec` / `.poland` | Показать развлекательный текст. |
| `.restart` | Перезапустить userbot. |

Все команды также работают с префиксом `!`.

## Модули из Telegram

1. Отправьте `.py`-файл в Telegram.
2. Ответьте на него командой `.dlmod`.
3. Прочитайте код и сверьте показанный SHA256.
4. Выполните `.dlmod confirm <sha256>` для установки.

Удаление: `.delmod <имя без .py>`.

Модуль выполняется с правами процесса userbot. SHA256 подтверждает неизменность файла после просмотра, но не доказывает безопасность кода.

## Обновление

```bash
git pull
python3 -m pip install -U -r requirements.txt
```

После обновления выполните `.restart` или `sudo systemctl restart userbot`.

Не заменяйте `config.py` и `*.session`.

## Docker Compose

```bash
cp config.example.py config.py
docker compose build
docker compose run --rm userbot python install.py
docker compose up -d
```

На вопрос о systemd во время контейнерной авторизации ответьте `n`.

```bash
docker compose logs -f
docker compose restart
docker compose down
```

Проект монтируется в `/app`, поэтому `config.py`, сессия и установленные модули сохраняются на хосте.

## Spotify Refresh Token

1. Создайте приложение в [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Добавьте Redirect URI `https://www.google.com/`.
3. Откройте ссылку, заменив `ВАШ_CLIENT_ID`:

```text
https://accounts.spotify.com/authorize?client_id=ВАШ_CLIENT_ID&response_type=code&redirect_uri=https://www.google.com/&scope=user-read-currently-playing%20user-read-playback-state
```

4. После подтверждения скопируйте параметр `code` из адресной строки.
5. Обменяйте код на refresh token:

```python
import base64
import requests

CLIENT_ID = "ВАШ_CLIENT_ID"
CLIENT_SECRET = "ВАШ_CLIENT_SECRET"
CODE = "КОД_ИЗ_АДРЕСНОЙ_СТРОКИ"

authorization = base64.b64encode(
    f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
).decode()

response = requests.post(
    "https://accounts.spotify.com/api/token",
    headers={"Authorization": f"Basic {authorization}"},
    data={
        "grant_type": "authorization_code",
        "code": CODE,
        "redirect_uri": "https://www.google.com/",
    },
    timeout=15,
)
response.raise_for_status()
print(response.json()["refresh_token"])
```

Код авторизации действует около 10 минут. Запишите результат в `SPOTIFY_REFRESH_TOKEN`.

<br>

**AI-generated.**<br>
*Использовались модели: Claude 4.6 Sonnet и Gemini 3.1 Pro.*
