"""Тесты хендлеров modules/manager.py — установка и удаление модулей.

Pyrogram/config в тестовой среде не нужны: внешние границы заменены заглушками,
вся проверяемая логика (пути, карантин, подтверждение) — собственная.

Запуск:      python -m unittest test_manager -v
Проверка RED: MANAGER_PATH=<путь к уязвимой версии> python -m unittest test_manager
"""

import io
import os
import sys
import types
import shutil
import asyncio
import hashlib
import tempfile
import importlib.util
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.abspath(__file__))
MANAGER_PATH = os.environ.get("MANAGER_PATH", os.path.join(REPO, "modules", "manager.py"))

PAYLOAD = b"__MODULE__ = 'Test'\n__HELP__ = 'test'\nprint('module loaded')\n"
PAYLOAD_SHA256 = hashlib.sha256(PAYLOAD).hexdigest()


# --- заглушки внешних границ (pyrogram, utils) ---

def install_stubs():
    if "pyrogram" in sys.modules:
        return

    class Filter:
        def __and__(self, other):
            return self

    filters = types.ModuleType("pyrogram.filters")
    filters.command = lambda *a, **k: Filter()
    filters.me = Filter()

    class Client:
        @staticmethod
        def on_message(*a, **k):
            return lambda fn: fn

    pyrogram = types.ModuleType("pyrogram")
    pyrogram.Client = Client
    pyrogram.filters = filters

    pyro_types = types.ModuleType("pyrogram.types")
    pyro_types.Message = type("Message", (), {})

    utils = types.ModuleType("utils")
    utils.ONLY_ME = Filter()

    sys.modules.update({
        "pyrogram": pyrogram,
        "pyrogram.filters": filters,
        "pyrogram.types": pyro_types,
        "utils": utils,
    })


def load_manager():
    install_stubs()
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    spec = importlib.util.spec_from_file_location("manager_under_test", MANAGER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["manager_under_test"] = module
    spec.loader.exec_module(module)
    return module


class FakeDocument:
    def __init__(self, file_name):
        self.file_name = file_name


class FakeMessage:
    def __init__(self, text, document_name=None):
        self.text = text
        self.command = text.lstrip(".").split()
        self.reply_to_message = None
        if document_name is not None:
            self.reply_to_message = types.SimpleNamespace(document=FakeDocument(document_name))
        self.edits = []

    async def edit(self, text):
        self.edits.append(text)

    @property
    def last_edit(self):
        return self.edits[-1] if self.edits else ""


class FakeClient:
    """Повторяет поведение pyrogram.Client.download_media (pyrofork 2.3.69).

    in_memory=True  -> BytesIO, на диск ничего не пишется.
    file_name=<path> -> запись по указанному пути; '..' не нормализуется —
                        именно это и делало старую версию уязвимой.
    """

    def __init__(self, payload=PAYLOAD):
        self.payload = payload

    async def download_media(self, message, file_name=None, in_memory=False):
        if in_memory:
            buffer = io.BytesIO(self.payload)
            buffer.name = "download"
            return buffer
        directory = os.path.dirname(file_name)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(file_name, "wb") as handle:
            handle.write(self.payload)
        return file_name


class ManagerTestCase(unittest.TestCase):
    def setUp(self):
        self.manager = load_manager()
        self.workdir = tempfile.mkdtemp(prefix="userbot-test-")
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)

        self.modules_dir = os.path.join(self.workdir, "modules")
        self.pending_dir = os.path.join(self.workdir, ".pending_modules")
        os.makedirs(self.modules_dir)

        # Файл-жертва за пределами modules/ — цель обхода пути.
        self.core_file = os.path.join(self.workdir, "main.py")
        with open(self.core_file, "w") as handle:
            handle.write("ORIGINAL CORE")

        previous_cwd = os.getcwd()
        os.chdir(self.workdir)
        self.addCleanup(os.chdir, previous_cwd)

        for name, value in [("MODULES_DIR", self.modules_dir), ("PENDING_DIR", self.pending_dir)]:
            if hasattr(self.manager, name):
                self.addCleanup(setattr, self.manager, name, getattr(self.manager, name))
                setattr(self.manager, name, value)
        if hasattr(self.manager, "_pending"):
            self.manager._pending.clear()

        self.execl = mock.patch("os.execl").start()
        self.addCleanup(mock.patch.stopall)

    def run_handler(self, handler, msg, client=None):
        asyncio.run(handler(client or FakeClient(), msg))
        return msg

    def core_file_contents(self):
        with open(self.core_file) as handle:
            return handle.read()


class DlmodRejectsHostileFilenames(ManagerTestCase):
    """Имя файла задаёт отправитель документа — это недоверенный ввод."""

    def test_parent_traversal_does_not_overwrite_core_file(self):
        msg = self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod", "../main.py"))

        self.assertEqual(self.core_file_contents(), "ORIGINAL CORE")
        self.assertNotIn("main.py", os.listdir(self.modules_dir))
        self.assertIn("Недопустимое", msg.last_edit)

    def test_parent_traversal_does_not_restart_the_bot(self):
        self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod", "../main.py"))
        self.execl.assert_not_called()

    def test_deep_traversal_writes_nothing_outside_workdir(self):
        self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod", "../../evil.py"))

        escaped = os.path.abspath(os.path.join(self.workdir, "..", "..", "evil.py"))
        self.assertFalse(os.path.exists(escaped))

    def test_non_python_document_is_refused(self):
        msg = self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod", "payload.txt"))
        self.assertEqual(os.listdir(self.modules_dir), [])
        self.assertNotIn("установлен!", msg.last_edit)

    def test_reply_without_document_is_refused(self):
        msg = self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod"))
        self.assertIn("Ответьте на файл", msg.last_edit)
        self.execl.assert_not_called()


class DlmodQuarantinesBeforeInstalling(ManagerTestCase):
    """Скачивание не должно приводить к исполнению кода без подтверждения."""

    def test_valid_module_is_not_installed_on_download(self):
        self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod", "weather.py"))
        self.assertFalse(os.path.exists(os.path.join(self.modules_dir, "weather.py")))

    def test_valid_module_lands_in_quarantine(self):
        self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod", "weather.py"))

        quarantined = os.path.join(self.pending_dir, "weather.py")
        self.assertTrue(os.path.exists(quarantined))
        with open(quarantined, "rb") as handle:
            self.assertEqual(handle.read(), PAYLOAD)

    def test_download_does_not_restart_the_bot(self):
        self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod", "weather.py"))
        self.execl.assert_not_called()

    def test_report_shows_sha256_for_review(self):
        msg = self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod", "weather.py"))
        self.assertIn(PAYLOAD_SHA256, msg.last_edit)

    def test_report_shows_file_preview(self):
        msg = self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod", "weather.py"))
        self.assertIn("print(&#x27;module loaded&#x27;)", msg.last_edit)

    def test_preview_escapes_html_so_markup_cannot_be_injected(self):
        client = FakeClient(payload=b"# <b>bold</b> <script>x</script>\n")
        msg = self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod", "weather.py"), client)

        self.assertNotIn("<b>bold</b>", msg.last_edit)
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", msg.last_edit)


class DlmodConfirmGate(ManagerTestCase):
    def download(self, name="weather.py", client=None):
        return self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod", name), client)

    def confirm(self, digest):
        return self.run_handler(self.manager.dlmod_handler, FakeMessage(f".dlmod confirm {digest}"))

    def test_correct_hash_installs_module(self):
        self.download()
        self.confirm(PAYLOAD_SHA256)

        installed = os.path.join(self.modules_dir, "weather.py")
        self.assertTrue(os.path.exists(installed))
        with open(installed, "rb") as handle:
            self.assertEqual(handle.read(), PAYLOAD)

    def test_correct_hash_restarts_the_bot(self):
        self.download()
        self.confirm(PAYLOAD_SHA256)
        self.execl.assert_called_once()

    def test_install_empties_the_quarantine(self):
        self.download()
        self.confirm(PAYLOAD_SHA256)
        self.assertFalse(os.path.exists(os.path.join(self.pending_dir, "weather.py")))

    def test_wrong_hash_does_not_install(self):
        self.download()
        msg = self.confirm("0" * 64)

        self.assertFalse(os.path.exists(os.path.join(self.modules_dir, "weather.py")))
        self.execl.assert_not_called()
        self.assertIn("не найден", msg.last_edit)

    def test_confirm_without_prior_download_does_nothing(self):
        msg = self.confirm(PAYLOAD_SHA256)

        self.assertEqual(os.listdir(self.modules_dir), [])
        self.execl.assert_not_called()
        self.assertIn("не найден", msg.last_edit)

    def test_confirm_without_hash_does_nothing(self):
        self.download()
        self.run_handler(self.manager.dlmod_handler, FakeMessage(".dlmod confirm"))

        self.assertFalse(os.path.exists(os.path.join(self.modules_dir, "weather.py")))
        self.execl.assert_not_called()

    def test_content_swapped_after_review_is_not_installed(self):
        """Хеш — проверка целостности, а не просто ключ поиска."""
        self.download()
        with open(os.path.join(self.pending_dir, "weather.py"), "wb") as handle:
            handle.write(b"# swapped after review\n")

        msg = self.confirm(PAYLOAD_SHA256)

        self.assertFalse(os.path.exists(os.path.join(self.modules_dir, "weather.py")))
        self.execl.assert_not_called()
        self.assertIn("изменилось", msg.last_edit)

    def test_second_download_of_same_name_invalidates_the_first_hash(self):
        """Атака: второй .dlmod перезаписывает карантин, старый хеш не должен установить новый файл."""
        self.download()
        malicious = b"# malicious replacement\n"
        self.download(client=FakeClient(payload=malicious))

        self.confirm(PAYLOAD_SHA256)

        installed = os.path.join(self.modules_dir, "weather.py")
        self.assertFalse(os.path.exists(installed), "установлен непроверенный модуль")
        self.execl.assert_not_called()

    def test_hash_of_the_actually_downloaded_file_still_installs(self):
        self.download()
        malicious = b"# malicious replacement\n"
        self.download(client=FakeClient(payload=malicious))

        self.confirm(hashlib.sha256(malicious).hexdigest())

        with open(os.path.join(self.modules_dir, "weather.py"), "rb") as handle:
            self.assertEqual(handle.read(), malicious)


class DelmodRejectsHostilePaths(ManagerTestCase):
    def test_traversal_does_not_delete_core_file(self):
        msg = self.run_handler(self.manager.delmod_handler, FakeMessage(".delmod ../main.py"))

        self.assertTrue(os.path.exists(self.core_file))
        self.assertEqual(self.core_file_contents(), "ORIGINAL CORE")
        self.assertIn("Недопустимое", msg.last_edit)

    def test_traversal_does_not_restart_the_bot(self):
        self.run_handler(self.manager.delmod_handler, FakeMessage(".delmod ../main"))
        self.execl.assert_not_called()

    def test_absolute_path_is_refused(self):
        victim = os.path.join(self.workdir, "victim.py")
        with open(victim, "w") as handle:
            handle.write("keep me")

        self.run_handler(self.manager.delmod_handler, FakeMessage(f".delmod {victim}"))
        self.assertTrue(os.path.exists(victim))

    def test_missing_argument_is_refused(self):
        msg = self.run_handler(self.manager.delmod_handler, FakeMessage(".delmod"))
        self.assertIn("Укажите название", msg.last_edit)
        self.execl.assert_not_called()


class DelmodRemovesRealModules(ManagerTestCase):
    def setUp(self):
        super().setUp()
        self.module_file = os.path.join(self.modules_dir, "poland.py")
        with open(self.module_file, "w") as handle:
            handle.write("# module")

    def test_removes_module_by_bare_name(self):
        self.run_handler(self.manager.delmod_handler, FakeMessage(".delmod poland"))
        self.assertFalse(os.path.exists(self.module_file))

    def test_removes_module_by_full_name(self):
        self.run_handler(self.manager.delmod_handler, FakeMessage(".delmod poland.py"))
        self.assertFalse(os.path.exists(self.module_file))

    def test_restarts_after_successful_removal(self):
        self.run_handler(self.manager.delmod_handler, FakeMessage(".delmod poland"))
        self.execl.assert_called_once()

    def test_unknown_module_reports_not_found_without_restart(self):
        msg = self.run_handler(self.manager.delmod_handler, FakeMessage(".delmod nosuchmodule"))

        self.assertIn("не найден", msg.last_edit)
        self.execl.assert_not_called()


if __name__ == "__main__":
    unittest.main()
