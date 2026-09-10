import unittest

from tests.stubs import install_pyrogram_stubs

install_pyrogram_stubs()


class InfoIPTest(unittest.TestCase):
    def test_normalize_ip_accepts_ipv4_and_ipv6(self):
        from modules.infoip import normalize_ip

        self.assertEqual(normalize_ip("1.1.1.1"), "1.1.1.1")
        self.assertEqual(normalize_ip("2001:0db8::1"), "2001:db8::1")

    def test_normalize_ip_rejects_hostnames(self):
        from modules.infoip import normalize_ip

        with self.assertRaises(ValueError):
            normalize_ip("example.com")

    def test_format_ip_info_escapes_external_values(self):
        from modules.infoip import format_ip_info

        text = format_ip_info({
            "ip": "1.1.1.1",
            "region": "<b>bad</b>",
            "city": "Sydney",
            "country": "Australia",
            "country_code": "AU",
            "continent": "Oceania",
            "postal": "2000",
            "latitude": -33.86,
            "longitude": 151.2,
            "connection": {"org": "Cloudflare"},
            "currency": {"code": "AUD", "symbol": "$"},
            "timezone": {"id": "Australia/Sydney"},
        })

        self.assertIn("&lt;b&gt;bad&lt;/b&gt;", text)
        self.assertNotIn("<b>bad</b>", text)

    def test_format_ip_info_rejects_invalid_nested_objects(self):
        from modules.infoip import format_ip_info

        for invalid in (None, "invalid", "", [], 0, False):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                format_ip_info({"connection": invalid})


if __name__ == "__main__":
    unittest.main()
