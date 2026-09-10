import sys
import types


class DummyFilter:
    def __and__(self, other):
        return self


class DummyClient:
    @staticmethod
    def on_message(*args, **kwargs):
        return lambda func: func


class DummyFilters:
    me = DummyFilter()

    @staticmethod
    def command(*args, **kwargs):
        return DummyFilter()


class DummyMessage:
    pass


class DummyFloodWait(Exception):
    def __init__(self, value=0):
        self.value = value


def install_pyrogram_stubs():
    pyrogram = types.ModuleType("pyrogram")
    pyrogram.Client = DummyClient
    pyrogram.filters = DummyFilters()

    pyrogram_types = types.ModuleType("pyrogram.types")
    pyrogram_types.Message = DummyMessage

    pyrogram_errors = types.ModuleType("pyrogram.errors")
    pyrogram_errors.FloodWait = DummyFloodWait
    pyrogram_errors.MessageNotModified = type("MessageNotModified", (Exception,), {})

    sys.modules.setdefault("pyrogram", pyrogram)
    sys.modules.setdefault("pyrogram.types", pyrogram_types)
    sys.modules.setdefault("pyrogram.errors", pyrogram_errors)

    config = types.ModuleType("config")
    config.api_id = 1
    config.api_hash = "test"
    config.DEFAULT_CITY = "Moscow"
    config.SPOTIFY_CLIENT_ID = ""
    config.SPOTIFY_CLIENT_SECRET = ""
    config.SPOTIFY_REFRESH_TOKEN = ""
    sys.modules.setdefault("config", config)
