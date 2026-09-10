import asyncio
import socket
import unittest
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tests.stubs import install_pyrogram_stubs

install_pyrogram_stubs()


class FakeResponse:
    def __init__(self, data=None, status=200, url="https://example.test"):
        self.data = data
        self.status = status
        self.url = url

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self, content_type=None):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.get(url)
        if response is None:
            return FakeResponse(status=404, url=url)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, tuple):
            return FakeResponse(response[0], url=response[1])
        return FakeResponse(response, url=url)


class TargetTest(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_public_ipv4_and_ipv6_without_dns(self):
        from services.ip_lookup import resolve_target

        resolver = AsyncMock()
        self.assertEqual((await resolve_target("1.1.1.1", resolver)).ips, ("1.1.1.1",))
        self.assertEqual(
            (await resolve_target("2606:4700:4700::1111", resolver)).ips,
            ("2606:4700:4700::1111",),
        )
        resolver.assert_not_called()

    async def test_rejects_non_public_literal_before_network(self):
        from services.ip_lookup import InvalidTarget, resolve_target

        resolver = AsyncMock()
        for target in ("127.0.0.1", "10.0.0.1", "169.254.1.1", "224.0.0.1", "::1", "fc00::1"):
            with self.subTest(target=target), self.assertRaises(InvalidTarget):
                await resolve_target(target, resolver)
        resolver.assert_not_called()

    async def test_idna_domain_resolves_unique_a_then_aaaa(self):
        from services.ip_lookup import resolve_target

        calls = []

        async def resolver(host, family):
            calls.append((host, family))
            if family == socket.AF_INET:
                return ["1.1.1.1", "8.8.8.8", "1.1.1.1"]
            return ["2606:4700:4700::1111", "2001:4860:4860::8888"]

        target = await resolve_target("BÜCHER.example.", resolver)

        self.assertEqual(target.host, "xn--bcher-kva.example")
        self.assertEqual(
            target.ips,
            ("1.1.1.1", "8.8.8.8", "2606:4700:4700::1111", "2001:4860:4860::8888"),
        )
        self.assertEqual(calls, [("xn--bcher-kva.example", socket.AF_INET), ("xn--bcher-kva.example", socket.AF_INET6)])

    async def test_dns_family_failure_preserves_other_family(self):
        from services.ip_lookup import resolve_target

        async def resolver(host, family):
            if family == socket.AF_INET:
                raise socket.gaierror("no A records")
            return ["2606:4700:4700::1111"]

        target = await resolve_target("ipv6.example", resolver)

        self.assertEqual(target.ips, ("2606:4700:4700::1111",))

    async def test_rejects_invalid_domain_and_private_dns_result(self):
        from services.ip_lookup import InvalidTarget, resolve_target

        async def private_resolver(host, family):
            return ["192.168.1.2"] if family == socket.AF_INET else []

        for target in ("https://example.com", "bad_name.example", "-bad.example", "example..com"):
            with self.subTest(target=target), self.assertRaises(InvalidTarget):
                await resolve_target(target, private_resolver)
        with self.assertRaises(InvalidTarget):
            await resolve_target("example.com", private_resolver)


class LookupTest(unittest.IsolatedAsyncioTestCase):
    def test_parses_real_ripe_string_asn_schema_safely(self):
        from services.ip_lookup import parse_asn

        self.assertEqual(parse_asn({"data": {"prefix": "1.1.1.0/24", "asns": ["13335"]}}), 13335)
        for value in ("", "0", "-1", "1.5", "AS13335", "4294967296", None, {}, 0, -1, 4294967296):
            with self.subTest(value=value):
                self.assertIsNone(parse_asn({"data": {"asns": [value]}}))

    async def test_rdap_redirect_accepts_only_https_official_rir_final_url(self):
        from services.ip_lookup import _get_json

        accepted = FakeSession(
            {"https://rdap.org/ip/1.1.1.1": ({"name": "APNIC-LABS"}, "https://rdap.apnic.net/ip/1.1.1.1")}
        )
        rejected = FakeSession(
            {"https://rdap.org/ip/1.1.1.1": ({"name": "stolen"}, "https://attacker.example/ip/1.1.1.1")}
        )

        self.assertEqual(
            await _get_json(accepted, "https://rdap.org/ip/1.1.1.1", rdap=True),
            {"name": "APNIC-LABS"},
        )
        self.assertIsNone(await _get_json(rejected, "https://rdap.org/ip/1.1.1.1", rdap=True))
        self.assertIsNone(await _get_json(accepted, "https://attacker.example/ip/1.1.1.1", rdap=True))
        self.assertEqual(accepted.calls[0][1]["allow_redirects"], True)
        self.assertEqual(accepted.calls[0][1]["max_redirects"], 5)
        self.assertEqual(accepted.calls[0][1]["headers"]["Accept"], "application/rdap+json")
        self.assertIn("Telegram-UserBot", accepted.calls[0][1]["headers"]["User-Agent"])
        self.assertEqual(len(accepted.calls), 1)

    async def test_independent_initial_sources_start_concurrently(self):
        from services.ip_lookup import (
            IPINFO_BASE,
            IPREGISTRY_BASE,
            RDAP_BASE,
            RIPE_GEO_URL,
            RIPE_NETWORK_URL,
            lookup_ip,
        )

        gate = asyncio.Event()
        started = set()

        async def fetch(session, url, params=None, rdap=False):
            started.add(url)
            if url in {
                RIPE_NETWORK_URL,
                RIPE_GEO_URL,
                f"{IPINFO_BASE}/1.1.1.1/json",
                f"{IPREGISTRY_BASE}/1.1.1.1",
                f"{RDAP_BASE}/ip/1.1.1.1",
            }:
                await gate.wait()
            if url == RIPE_NETWORK_URL:
                return {"data": {"prefix": "1.1.1.0/24", "asns": ["13335"]}}
            return None

        with patch("services.ip_lookup._get_json", side_effect=fetch):
            task = asyncio.create_task(
                lookup_ip(FakeSession({}), "1.1.1.1", SimpleNamespace(IPINFO_TOKEN="token", IPREGISTRY_KEY="key"))
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.assertEqual(
                started,
                {
                    RIPE_NETWORK_URL,
                    RIPE_GEO_URL,
                    f"{IPINFO_BASE}/1.1.1.1/json",
                    f"{IPREGISTRY_BASE}/1.1.1.1",
                    f"{RDAP_BASE}/ip/1.1.1.1",
                },
            )
            gate.set()
            await task

    def test_local_maxmind_city_and_asn_fail_independently(self):
        from services.ip_lookup import _local_maxmind

        city_record = SimpleNamespace(
            country=SimpleNamespace(iso_code="AU", name="Australia"),
            city=SimpleNamespace(name="Sydney"),
            subdivisions=SimpleNamespace(most_specific=SimpleNamespace(name="New South Wales")),
            location=SimpleNamespace(latitude=-33.8, longitude=151.2),
        )
        asn_record = SimpleNamespace(autonomous_system_number=13335, autonomous_system_organization="Cloudflare, Inc.")

        class Reader:
            def __init__(self, path):
                self.path = path

            def __enter__(self):
                if self.path == "broken.mmdb":
                    raise OSError("broken")
                return self

            def __exit__(self, *args):
                return False

            def city(self, ip):
                return city_record

            def asn(self, ip):
                return asn_record

        database = types.ModuleType("geoip2.database")
        database.Reader = Reader
        geoip2 = types.ModuleType("geoip2")
        geoip2.database = database
        with patch.dict(sys.modules, {"geoip2": geoip2, "geoip2.database": database}):
            city_only = _local_maxmind("1.1.1.1", "city.mmdb", "broken.mmdb")
            asn_only = _local_maxmind("1.1.1.1", "broken.mmdb", "asn.mmdb")

        self.assertEqual(city_only.values["city"], "Sydney")
        self.assertNotIn("asn", city_only.values)
        self.assertEqual(asn_only.values["asn"], 13335)
        self.assertNotIn("city", asn_only.values)

    async def test_local_geolite_asn_fills_missing_ripe_asn(self):
        from services.ip_lookup import SourceData, lookup_ip

        responses = {
            "https://stat.ripe.net/data/network-info/data.json": {"data": {"prefix": "1.1.1.0/24", "asns": []}},
            "https://rdap.org/ip/1.1.1.1": {"port43": "whois.apnic.net", "name": "APNIC-LABS"},
        }
        local = SourceData("Available", {"country": "AU", "asn": 13335, "organization": "Cloudflare"})
        config = SimpleNamespace(MAXMIND_CITY_DB="city.mmdb", MAXMIND_ASN_DB="asn.mmdb")

        with patch("services.ip_lookup._local_maxmind", return_value=local):
            result = await lookup_ip(FakeSession(responses), "1.1.1.1", config)

        self.assertEqual(result.asn, 13335)
        self.assertEqual(result.organization, "Cloudflare")

    async def test_local_asn_only_uses_remote_maxmind_geo_fallback(self):
        from services.ip_lookup import SourceData, lookup_ip

        responses = {
            "https://stat.ripe.net/data/network-info/data.json": {"data": {"prefix": "1.1.1.0/24", "asns": []}},
            "https://stat.ripe.net/data/maxmind-geo-lite/data.json": {
                "data": {"located_resources": [{"locations": [{"country": "AU", "city": "Sydney"}]}]}
            },
            "https://rdap.org/ip/1.1.1.1": {"port43": "whois.apnic.net", "name": "APNIC-LABS"},
        }
        local = SourceData("Available", {"asn": 13335, "organization": "Cloudflare"})

        with patch("services.ip_lookup._local_maxmind", return_value=local):
            result = await lookup_ip(
                FakeSession(responses),
                "1.1.1.1",
                SimpleNamespace(MAXMIND_ASN_DB="asn.mmdb"),
            )

        self.assertEqual(result.maxmind.status, "Available")
        self.assertEqual(result.maxmind.values["country"], "AU")
        self.assertEqual(result.maxmind.values["city"], "Sydney")

    async def test_uses_only_fixed_https_urls_and_preserves_partial_failures(self):
        from services.ip_lookup import lookup_ip

        responses = {
            "https://stat.ripe.net/data/network-info/data.json": {
                "data": {"prefix": "1.1.1.0/24", "asns": ["13335"]}
            },
            "https://stat.ripe.net/data/maxmind-geo-lite/data.json": RuntimeError("down"),
            "https://stat.ripe.net/data/as-overview/data.json": {
                "data": {"holder": "CLOUDFLARENET - Cloudflare, Inc."}
            },
            "https://rdap.org/ip/1.1.1.1": {
                "port43": "whois.apnic.net",
                "name": "APNIC-LABS",
                "country": "AU",
                "startAddress": "1.1.1.0",
                "endAddress": "1.1.1.255",
            },
            "https://rdap.org/autnum/13335": {"name": "CLOUDFLARENET", "country": "US"},
        }
        session = FakeSession(responses)
        result = await lookup_ip(session, "1.1.1.1", SimpleNamespace())

        self.assertEqual(result.prefix, "1.1.1.0/24")
        self.assertEqual(result.asn, 13335)
        self.assertEqual(result.maxmind.status, "Unavailable")
        self.assertEqual(result.ipinfo.status, "Not configured")
        self.assertEqual(result.privacy.status, "Not configured")
        self.assertEqual(result.registration.rir, "APNIC")
        for url, kwargs in session.calls:
            self.assertTrue(url.startswith("https://"))
            self.assertNotIn("1.1.1.1", url.split("?", 1)[0] if "stat.ripe.net" in url else "")
            if url.startswith("https://rdap.org/"):
                self.assertTrue(kwargs["allow_redirects"])
            else:
                self.assertFalse(kwargs.get("allow_redirects", True))

    async def test_optional_sources_distinguish_success_and_failure(self):
        from services.ip_lookup import lookup_ip

        responses = {
            "https://stat.ripe.net/data/network-info/data.json": {"data": {"prefix": "8.8.8.0/24", "asns": ["15169"]}},
            "https://stat.ripe.net/data/maxmind-geo-lite/data.json": {"data": {"located_resources": [{"locations": [{"country": "US", "city": "Mountain View"}]}]}},
            "https://stat.ripe.net/data/as-overview/data.json": {"data": {"holder": "GOOGLE"}},
            "https://rdap.org/ip/8.8.8.8": {"port43": "whois.arin.net", "name": "GOGL", "country": "US"},
            "https://rdap.org/autnum/15169": {"name": "GOOGLE", "country": "US"},
            "https://ipinfo.io/8.8.8.8/json": {"city": "Mountain View", "region": "California", "country": "US", "loc": "37.4,-122.1", "anycast": True},
            "https://api.ipregistry.co/8.8.8.8": RuntimeError("down"),
        }
        result = await lookup_ip(
            FakeSession(responses),
            "8.8.8.8",
            SimpleNamespace(IPINFO_TOKEN="token", IPREGISTRY_KEY="key"),
        )

        self.assertTrue(result.anycast)
        self.assertEqual(result.ipinfo.status, "Available")
        self.assertEqual(result.privacy.status, "Unavailable")

    async def test_current_ipinfo_legacy_schema_sets_anycast_and_as_website(self):
        from services.ip_lookup import lookup_ip

        responses = {
            "https://stat.ripe.net/data/network-info/data.json": {
                "data": {"prefix": "8.8.8.0/24", "asns": ["15169"]}
            },
            "https://stat.ripe.net/data/as-overview/data.json": {"data": {"holder": "GOOGLE - Google LLC"}},
            "https://ipinfo.io/8.8.8.8/json": {
                "city": "Mountain View",
                "region": "California",
                "country": "US",
                "loc": "37.4,-122.1",
                "is_anycast": True,
                "asn": {"domain": "google.com"},
            },
            "https://rdap.org/ip/8.8.8.8": {"port43": "whois.arin.net", "name": "GOGL", "country": "US"},
            "https://rdap.org/autnum/15169": {"name": "GOOGLE", "country": "US"},
        }

        result = await lookup_ip(
            FakeSession(responses),
            "8.8.8.8",
            SimpleNamespace(IPINFO_TOKEN="token"),
        )

        self.assertTrue(result.anycast)
        self.assertEqual(result.registration.website, "https://google.com")

    async def test_real_schemas_normalize_org_registration_and_reuse_ipregistry(self):
        from services.ip_lookup import lookup_ip

        responses = {
            "https://stat.ripe.net/data/network-info/data.json": {"data": {"prefix": "1.1.1.0/24", "asns": ["13335"]}},
            "https://stat.ripe.net/data/maxmind-geo-lite/data.json": {"data": {"located_resources": [{"resource": "1.1.1.1", "locations": [{"country": "?", "city": "Sydney"}]}]}},
            "https://stat.ripe.net/data/as-overview/data.json": {"data": {"holder": "CLOUDFLARENET - Cloudflare, Inc."}},
            "https://ipinfo.io/1.1.1.1/json": {"country": "AU", "city": "Sydney", "region": "New South Wales", "anycast": True, "hostname": "one.one.one.one"},
            "https://api.ipregistry.co/1.1.1.1": {
                "location": {"country": {"code": "AU", "name": "Australia"}, "city": "Sydney", "region": {"name": "New South Wales"}},
                "connection": {"domain": "cloudflare.com"},
                "security": {"is_proxy": False, "is_abuser": False, "is_cloud_provider": True},
            },
            "https://rdap.org/ip/1.1.1.1": ({
                "port43": "whois.apnic.net",
                "name": "APNIC-LABS",
                "country": "AU",
                "entities": [{"roles": ["registrant"], "vcardArray": ["vcard", [["org", {}, "text", "APNIC Pty Ltd"]]]}],
            }, "https://rdap.apnic.net/ip/1.1.1.1"),
            "https://rdap.org/autnum/13335": ({
                "name": "CLOUDFLARENET",
                "country": "US",
                "entities": [{"roles": ["registrant"], "vcardArray": ["vcard", [["fn", {}, "text", "Abuse contact"], ["org", {}, "text", "Cloudflare, Inc."]]]}],
            }, "https://rdap.arin.net/registry/autnum/13335"),
        }
        session = FakeSession(responses)

        result = await lookup_ip(
            session,
            "1.1.1.1",
            SimpleNamespace(IPINFO_TOKEN="token", IPREGISTRY_KEY="key"),
        )

        self.assertEqual(result.asn, 13335)
        self.assertEqual(result.organization, "Cloudflare, Inc.")
        self.assertEqual(result.maxmind.values["country"], "AU")
        self.assertEqual(result.registration.organization, "Cloudflare, Inc.")
        self.assertEqual(result.registration.website, "https://cloudflare.com")
        self.assertEqual(result.privacy.values, {"proxy": False, "abuser": False, "server": True})
        registry_calls = [url for url, _ in session.calls if url.startswith("https://api.ipregistry.co/")]
        self.assertEqual(registry_calls, ["https://api.ipregistry.co/1.1.1.1"])


class FormatTest(unittest.TestCase):
    def _result(self, ip="2606:4700:4700::1111", city="Sydney", anycast=True):
        from services.ip_lookup import IPResult, SourceData, Registration

        return IPResult(
            ip=ip,
            prefix="2606:4700::/32",
            asn=13335,
            organization="Cloudflare, Inc.",
            anycast=anycast,
            maxmind=SourceData("Available", {"country": "AU", "country_name": "Australia", "region": "New South Wales", "city": city}),
            ipinfo=SourceData("Available", {"country": "AU", "country_name": "Australia", "region": "New South Wales", "city": city}),
            registration=Registration(
                rir="APNIC",
                network_name="APNIC-LABS",
                country="AU",
                as_name="CLOUDFLARENET",
                as_country="US",
                organization="Cloudflare, Inc.",
                website="https://www.cloudflare.com",
            ),
            privacy=SourceData("Available", {"proxy": False, "abuser": False, "server": True}),
        )

    def test_golden_group_renders_each_ipv6_and_one_shared_section(self):
        from services.ip_lookup import format_group, render_chunks

        text = format_group(
            [self._result(), self._result("2606:4700:4700::1001")],
            host="one.one.one.one",
        )

        expected = """🔗 Host: one.one.one.one (<a href="https://info.addr.tools/one.one">Whois</a>?)
------------------------
IP: 2606:4700:4700::1111 is anycast 🚀
<a href="https://bgp.tools/prefix/2606%3A4700%3A%3A/32">BGP</a> | <a href="https://platform.censys.io/hosts/2606%3A4700%3A4700%3A%3A1111">Censys</a> | <a href="https://ipinfo.io/2606%3A4700%3A4700%3A%3A1111">IPinfo</a> | <a href="https://www.ipqualityscore.com/free-ip-lookup-proxy-vpn-test/lookup/2606%3A4700%3A4700%3A%3A1111">IPQS</a> | <a href="https://ipregion.xyz/2606%3A4700%3A4700%3A%3A1111">More</a>
IP: 2606:4700:4700::1001 is anycast 🚀
<a href="https://bgp.tools/prefix/2606%3A4700%3A%3A/32">BGP</a> | <a href="https://platform.censys.io/hosts/2606%3A4700%3A4700%3A%3A1001">Censys</a> | <a href="https://ipinfo.io/2606%3A4700%3A4700%3A%3A1001">IPinfo</a> | <a href="https://www.ipqualityscore.com/free-ip-lookup-proxy-vpn-test/lookup/2606%3A4700%3A4700%3A%3A1001">IPQS</a> | <a href="https://ipregion.xyz/2606%3A4700%3A4700%3A%3A1001">More</a>
------------------------
▢ MaxMind:
🇦🇺 AU Australia, New South Wales, Sydney
AS13335 / Cloudflare, Inc.

▢ IPinfo & Cloudflare:
🇦🇺 AU Australia, New South Wales, Sydney
AS13335 / Cloudflare, Inc.

▢ Registration (APNIC):
🇦🇺 AU Australia (IP)
APNIC-LABS
🇺🇸 US United States (AS)
<a href="https://www.cloudflare.com">CLOUDFLARENET</a> / Cloudflare, Inc.

▢ Privacy info (ipregistry․co):
Proxy ❌ | Abuser ❌ | Server ✅"""
        self.assertEqual(text, expected)
        self.assertEqual(render_chunks([self._result(), self._result("2606:4700:4700::1001")], host="one.one.one.one"), [expected])

    def test_missing_geo_has_exact_no_data_line(self):
        from dataclasses import replace
        from services.ip_lookup import SourceData, format_group

        for country in (None, "?", "1!"):
            with self.subTest(country=country):
                result = replace(self._result(), maxmind=SourceData("Available", {"country": country, "city": "Nowhere"}))
                self.assertIn("▢ MaxMind:\n🏳 No geo data\nAS13335 / Cloudflare, Inc.", format_group([result]))

    def test_groups_only_identical_enrichment_and_splits_at_boundaries(self):
        from services.ip_lookup import group_results, render_chunks

        first = self._result()
        same = self._result("2606:4700:4700::1001")
        different = self._result("2001:4860:4860::8888", city="Mountain View", anycast=False)
        groups = group_results([first, same, different])
        self.assertEqual([len(group) for group in groups], [2, 1])

        oversized_group = [self._result(f"2606:4700:4700::{index:x}") for index in range(1, 18)]
        chunks = render_chunks(oversized_group, host="one.one.one.one")
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 4096 for chunk in chunks))
        self.assertEqual(sum(chunk.count("IP: ") for chunk in chunks), 17)
        self.assertEqual(sum(chunk.count("▢ MaxMind:") for chunk in chunks), 1)

    def test_safe_links_quote_ipv6_and_registrable_domain_is_best_effort(self):
        from services.ip_lookup import registrable_domain, service_links

        links = service_links("2606:4700:4700::1111", "2606:4700::/32")
        self.assertIn("2606%3A4700%3A4700%3A%3A1111", links)
        self.assertIn("https://bgp.tools/prefix/2606%3A4700%3A%3A/32", links)
        self.assertEqual(registrable_domain("www.example.co.uk"), "example.co.uk")
        self.assertEqual(registrable_domain("xn--bcher-kva.example"), "xn--bcher-kva.example")


class HandlerTest(unittest.IsolatedAsyncioTestCase):
    async def test_handler_sends_each_rendered_chunk(self):
        import modules.infoip as module
        from services.ip_lookup import Target

        msg = SimpleNamespace(text=".ipi example.com", edit=AsyncMock(), reply_text=AsyncMock())
        fake_session = AsyncMock()
        session_context = AsyncMock()
        session_context.__aenter__.return_value = fake_session
        session_context.__aexit__.return_value = False

        with patch.object(module, "resolve_target", AsyncMock(return_value=Target("example.com", ("1.1.1.1",)))), patch.object(
            module, "lookup_ip", AsyncMock(return_value=object())
        ), patch.object(module, "render_chunks", return_value=["first", "second"]), patch.object(
            module.aiohttp, "ClientSession", return_value=session_context
        ):
            await module.info_ip_handler(None, msg)

        self.assertEqual(msg.edit.await_args_list[-1].args[0], "first")
        msg.reply_text.assert_awaited_once_with("second", disable_web_page_preview=True)


if __name__ == "__main__":
    unittest.main()
