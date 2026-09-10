import unittest

from tests.stubs import install_pyrogram_stubs

install_pyrogram_stubs()


class CodeBase64Test(unittest.TestCase):
    def test_round_trip_unicode_text(self):
        from modules.codebase64 import decode_text, encode_text

        encoded = encode_text("Привет")

        self.assertEqual(decode_text(encoded), "Привет")

    def test_decode_rejects_non_base64_input(self):
        from modules.codebase64 import decode_text

        with self.assertRaises(ValueError):
            decode_text("not base64!")

    def test_decode_rejects_non_utf8_bytes(self):
        from modules.codebase64 import decode_text

        with self.assertRaises(ValueError):
            decode_text("/w==")

    def test_fits_message_checks_escaped_telegram_length(self):
        from modules.codebase64 import fits_message

        self.assertTrue(fits_message("text"))
        self.assertFalse(fits_message("<" * 1000))


if __name__ == "__main__":
    unittest.main()
