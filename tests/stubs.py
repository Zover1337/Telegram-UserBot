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


def install_pyrogram_stubs():
    pyrogram = types.ModuleType("pyrogram")
    pyrogram.Client = DummyClient
    pyrogram.filters = DummyFilters()

    pyrogram_types = types.ModuleType("pyrogram.types")
    pyrogram_types.Message = DummyMessage

    sys.modules.setdefault("pyrogram", pyrogram)
    sys.modules.setdefault("pyrogram.types", pyrogram_types)

    config = types.ModuleType("config")
    config.api_id = 1
    config.api_hash = "test"
    config.DEFAULT_CITY = "Moscow"
    config.SPOTIFY_CLIENT_ID = ""
    config.SPOTIFY_CLIENT_SECRET = ""
    config.SPOTIFY_REFRESH_TOKEN = ""
    sys.modules.setdefault("config", config)
