"""Тесты guard'а путей модулей (paths.safe_module_path).

Запуск: python -m unittest test_paths -v
"""

import os
import unittest

from paths import safe_module_path

BASE = os.path.abspath("/srv/bot/modules")


class SafeModulePathRejectsHostileNames(unittest.TestCase):
    """Имя приходит из недоверенного источника — документа в Telegram."""

    def test_rejects_parent_directory_escape(self):
        self.assertIsNone(safe_module_path("../main.py", BASE))

    def test_rejects_multi_level_escape(self):
        self.assertIsNone(safe_module_path("../../utils.py", BASE))

    def test_rejects_escape_hidden_inside_path(self):
        self.assertIsNone(safe_module_path("modules/../main.py", BASE))

    def test_rejects_absolute_path(self):
        self.assertIsNone(safe_module_path("/etc/cron.d/payload.py", BASE))

    def test_rejects_subdirectory(self):
        self.assertIsNone(safe_module_path("a/b.py", BASE))

    def test_rejects_windows_separator(self):
        self.assertIsNone(safe_module_path("..\\main.py", BASE))


class SafeModulePathRejectsNonModules(unittest.TestCase):
    def test_rejects_non_python_extension(self):
        self.assertIsNone(safe_module_path("notes.txt", BASE))

    def test_rejects_dunder_file(self):
        self.assertIsNone(safe_module_path("__init__.py", BASE))

    def test_rejects_dotfile(self):
        self.assertIsNone(safe_module_path(".hidden.py", BASE))

    def test_rejects_bare_extension(self):
        self.assertIsNone(safe_module_path(".py", BASE))

    def test_rejects_empty_name(self):
        self.assertIsNone(safe_module_path("", BASE))

    def test_rejects_missing_name(self):
        self.assertIsNone(safe_module_path(None, BASE))


class SafeModulePathAcceptsPlainModules(unittest.TestCase):
    def test_returns_absolute_path_inside_base(self):
        self.assertEqual(safe_module_path("weather.py", BASE), os.path.join(BASE, "weather.py"))

    def test_accepts_name_with_digits_and_underscore(self):
        self.assertEqual(safe_module_path("my_mod2.py", BASE), os.path.join(BASE, "my_mod2.py"))

    def test_result_always_stays_directly_inside_base(self):
        for name in ["weather.py", "a.py", "very_long_module_name.py"]:
            path = safe_module_path(name, BASE)
            self.assertIsNotNone(path, name)
            self.assertEqual(os.path.dirname(path), BASE)


if __name__ == "__main__":
    unittest.main()
