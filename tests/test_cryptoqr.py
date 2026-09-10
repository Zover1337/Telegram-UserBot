import unittest

from tests.stubs import install_pyrogram_stubs

install_pyrogram_stubs()


class CryptoQRTest(unittest.TestCase):
    def test_build_qr_image_returns_png(self):
        from modules.cryptoqr import build_qr_image

        image = build_qr_image("https://example.com")

        self.assertTrue(image.getvalue().startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(image.name, "qrcode.png")

    def test_build_qr_image_rejects_payload_over_capacity(self):
        from modules.cryptoqr import build_qr_image

        with self.assertRaises(ValueError):
            build_qr_image("я" * 601)


if __name__ == "__main__":
    unittest.main()
