import os

MODULES_DIR = os.path.abspath("modules")
PENDING_DIR = os.path.abspath(".pending_modules")


def safe_module_path(raw_name, base):
    """Абсолютный путь к модулю внутри base, или None если имя недопустимо.

    Имя приходит из недоверенного источника (документ в Telegram, аргумент
    команды), поэтому путь из него отбрасывается целиком: берётся только
    basename, результат проверяется на принадлежность base.
    """
    name = raw_name or ""
    if name != os.path.basename(name) or os.path.sep in name or "/" in name or "\\" in name:
        return None
    if not name.endswith(".py") or name.startswith((".", "_")) or len(name) <= 3:
        return None
    path = os.path.abspath(os.path.join(base, name))
    if os.path.dirname(path) != os.path.abspath(base):
        return None
    return path
