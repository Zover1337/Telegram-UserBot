import unittest
import sys
import types

from tests.stubs import install_pyrogram_stubs

install_pyrogram_stubs()

pytz = types.ModuleType("pytz")
pytz.timezone = lambda value: value
sys.modules.setdefault("pytz", pytz)


class WeatherHelpTest(unittest.TestCase):
    def test_default_command_describes_configured_city(self):
        from modules import weather

        self.assertIn("Погода в Moscow", weather.__HELP__)
        self.assertNotIn("Погода в мск", weather.__HELP__)


if __name__ == "__main__":
    unittest.main()
