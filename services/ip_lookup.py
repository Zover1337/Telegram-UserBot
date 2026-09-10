import asyncio
import html
import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlsplit


RIPE_NETWORK_URL = "https://stat.ripe.net/data/network-info/data.json"
RIPE_GEO_URL = "https://stat.ripe.net/data/maxmind-geo-lite/data.json"
RIPE_AS_URL = "https://stat.ripe.net/data/as-overview/data.json"
RDAP_BASE = "https://rdap.org"
IPINFO_BASE = "https://ipinfo.io"
IPREGISTRY_BASE = "https://api.ipregistry.co"
RDAP_HOSTS = {
    "rdap.org",
    "rdap.afrinic.net",
    "rdap.apnic.net",
    "rdap.arin.net",
    "rdap.db.ripe.net",
    "rdap.lacnic.net",
}
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)
COMMON_SECOND_LEVEL = {"ac", "co", "com", "edu", "gov", "net", "org"}
SEPARATOR = "------------------------"
TEXT_LIMIT = 512
COUNTRY_NAME_FALLBACK = {"AU": "Australia", "US": "United States"}


class InvalidTarget(ValueError):
    pass


@dataclass(frozen=True)
class Target:
    host: str | None
    ips: tuple[str, ...]


@dataclass(frozen=True)
class SourceData:
    status: str
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Registration:
    rir: str = "Unknown"
    network_name: str = "Unknown"
    country: str = "Unknown"
    address_range: str = "Unknown"
    as_name: str = "Unknown"
    as_country: str = "Unknown"
    status: str = "Available"
    organization: str = "Unknown"
    website: str | None = None


@dataclass(frozen=True)
class IPResult:
    ip: str
    prefix: str = "Unknown"
    asn: int | None = None
    organization: str = "Unknown"
    anycast: bool = False
    maxmind: SourceData = field(default_factory=lambda: SourceData("Unavailable"))
    ipinfo: SourceData = field(default_factory=lambda: SourceData("Not configured"))
    registration: Registration = field(default_factory=Registration)
    privacy: SourceData = field(default_factory=lambda: SourceData("Not configured"))


def _public_ip(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise InvalidTarget("Invalid IP address") from exc
    if (
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise InvalidTarget("Only public IP addresses are supported")
    return str(address)


async def _system_resolver(host: str, family: int) -> list[str]:
    loop = asyncio.get_running_loop()
    records = await loop.getaddrinfo(host, None, family=family, type=socket.SOCK_STREAM)
    return [record[4][0] for record in records]


async def resolve_target(value: str, resolver=None) -> Target:
    raw = value.strip()
    if not raw or len(raw) > 253:
        raise InvalidTarget("Invalid target")
    try:
        return Target(None, (_public_ip(raw),))
    except InvalidTarget:
        try:
            ipaddress.ip_address(raw)
        except ValueError:
            pass
        else:
            raise

    try:
        host = raw.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise InvalidTarget("Invalid domain") from exc
    if not DOMAIN_RE.fullmatch(host):
        raise InvalidTarget("Invalid domain")

    resolver = resolver or _system_resolver
    addresses = []
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            for address in await resolver(host, family):
                normalized = _public_ip(address)
                if normalized not in addresses:
                    addresses.append(normalized)
        except OSError:
            continue
    if not addresses:
        raise InvalidTarget("Domain has no public A or AAAA records")
    return Target(host, tuple(addresses))


async def _get_json(session, url: str, params=None, rdap=False):
    if rdap:
        initial = urlsplit(url)
        if initial.scheme != "https" or initial.hostname != "rdap.org":
            return None
    request_options = {"params": params, "allow_redirects": rdap}
    if rdap:
        request_options["max_redirects"] = 5
        request_options["headers"] = {
            "Accept": "application/rdap+json",
            "User-Agent": "Telegram-UserBot/1.0",
        }
    try:
        async with session.get(url, **request_options) as response:
            if response.status != 200:
                return None
            if rdap:
                final = urlsplit(str(response.url))
                if final.scheme != "https" or final.hostname not in RDAP_HOSTS:
                    return None
            data = await response.json(content_type=None)
            return data if isinstance(data, dict) else None
    except Exception:
        return None


def parse_asn(network: dict) -> int | None:
    data = network.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("asns"), list) or not data["asns"]:
        return None
    value = data["asns"][0]
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 < value <= 4294967295 else None
    if isinstance(value, str) and value.isdecimal():
        parsed = int(value)
        return parsed if 0 < parsed <= 4294967295 else None
    return None


def _first_location(data: dict) -> dict:
    root = data.get("data")
    resources = root.get("located_resources") if isinstance(root, dict) else None
    if not isinstance(resources, list) or not resources or not isinstance(resources[0], dict):
        return {}
    locations = resources[0].get("locations")
    return locations[0] if isinstance(locations, list) and locations and isinstance(locations[0], dict) else {}


def _local_maxmind(ip: str, city_path: str | None, asn_path: str | None):
    if not city_path and not asn_path:
        return None
    try:
        import geoip2.database
    except Exception:
        return SourceData("Unavailable")

    values = {}
    successful = False
    if city_path:
        try:
            with geoip2.database.Reader(city_path) as reader:
                city = reader.city(ip)
                values.update(
                    country=city.country.iso_code,
                    country_name=city.country.name,
                    city=city.city.name,
                    region=city.subdivisions.most_specific.name,
                    coordinates=(
                        f"{city.location.latitude},{city.location.longitude}"
                        if city.location.latitude is not None and city.location.longitude is not None
                        else None
                    ),
                )
                successful = True
        except Exception:
            pass
    if asn_path:
        try:
            with geoip2.database.Reader(asn_path) as reader:
                record = reader.asn(ip)
                values.update(asn=record.autonomous_system_number, organization=record.autonomous_system_organization)
                successful = True
        except Exception:
            pass
    clean = {key: value for key, value in values.items() if value not in (None, "")}
    return SourceData("Available", clean) if successful else SourceData("Unavailable")


def _rir_from_rdap(data: dict) -> str:
    marker = f"{data.get('port43', '')} {data.get('name', '')}".lower()
    for name in ("ARIN", "RIPE", "APNIC", "LACNIC", "AFRINIC"):
        if name.lower() in marker:
            return name
    return "Unknown"


def _vcard_org(data: dict) -> str | None:
    entities = data.get("entities")
    if not isinstance(entities, list):
        return None
    rows = []
    for entity in entities:
        card = entity.get("vcardArray") if isinstance(entity, dict) else None
        if isinstance(card, list) and len(card) > 1 and isinstance(card[1], list):
            rows.extend(card[1])
    for field_name in ("org", "fn"):
        for row in rows:
            if isinstance(row, list) and len(row) > 3 and row[0] == field_name and isinstance(row[3], str):
                return row[3]
    return None


def _normalized_org(holder: Any) -> str:
    if not isinstance(holder, str) or not holder.strip():
        return "Unknown"
    left, separator, right = holder.partition(" - ")
    return (right if separator and right.strip() else left).strip()


def _domain_website(*domains: Any) -> str | None:
    for domain in domains:
        if not isinstance(domain, str) or not domain:
            continue
        candidate = domain if "://" in domain else f"https://{domain}"
        parsed = urlsplit(candidate)
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
            return f"https://{parsed.netloc}{parsed.path}".rstrip("/")
    return None


def _registry_location(registry: dict | None) -> dict:
    location = registry.get("location") if isinstance(registry, dict) else None
    if not isinstance(location, dict):
        return {}
    country = location.get("country") if isinstance(location.get("country"), dict) else {}
    region = location.get("region") if isinstance(location.get("region"), dict) else location.get("region")
    return {
        "country": country.get("code"),
        "country_name": country.get("name"),
        "region": region.get("name") if isinstance(region, dict) else region,
        "city": location.get("city"),
    }


def _merge_location(primary: dict, fallback: dict) -> dict:
    keys = ("country", "country_name", "region", "city", "coordinates")
    merged = {}
    for key in keys:
        value = primary.get(key)
        if value in (None, "", "?"):
            value = fallback.get(key)
        if value not in (None, "", "?"):
            merged[key] = value
    return merged


async def _ready(value):
    return value


async def lookup_ip(session, ip: str, config) -> IPResult:
    city_path = getattr(config, "MAXMIND_CITY_DB", None)
    asn_path = getattr(config, "MAXMIND_ASN_DB", None)
    local_maxmind = _local_maxmind(ip, city_path, asn_path)
    token = getattr(config, "IPINFO_TOKEN", None)
    registry_key = getattr(config, "IPREGISTRY_KEY", None)
    encoded_ip = quote(ip, safe="")
    local_geo = local_maxmind.values if local_maxmind and local_maxmind.status == "Available" else {}
    has_local_geo = any(local_geo.get(key) not in (None, "") for key in ("country", "region", "city", "coordinates"))

    network_coro = _get_json(session, RIPE_NETWORK_URL, {"resource": ip})
    geo_coro = _ready(None) if has_local_geo else _get_json(session, RIPE_GEO_URL, {"resource": ip})
    info_coro = _get_json(session, f"{IPINFO_BASE}/{encoded_ip}/json", {"token": token}) if token else _ready(None)
    registry_coro = _get_json(session, f"{IPREGISTRY_BASE}/{encoded_ip}", {"key": registry_key}) if registry_key else _ready(None)
    rdap_ip_coro = _get_json(session, f"{RDAP_BASE}/ip/{encoded_ip}", rdap=True)
    network, geo, info, registry, rdap_ip = await asyncio.gather(
        network_coro, geo_coro, info_coro, registry_coro, rdap_ip_coro
    )

    network = network or {}
    network_data = network.get("data") if isinstance(network.get("data"), dict) else {}
    prefix = network_data.get("prefix") if isinstance(network_data.get("prefix"), str) else "Unknown"
    asn = parse_asn(network)
    if asn is None and local_maxmind and isinstance(local_maxmind.values.get("asn"), int):
        asn = local_maxmind.values["asn"]

    as_overview_coro = _get_json(session, RIPE_AS_URL, {"resource": f"AS{asn}"}) if asn else _ready(None)
    rdap_as_coro = _get_json(session, f"{RDAP_BASE}/autnum/{asn}", rdap=True) if asn else _ready(None)
    as_overview, rdap_as = await asyncio.gather(as_overview_coro, rdap_as_coro)
    as_data = as_overview.get("data") if isinstance(as_overview, dict) and isinstance(as_overview.get("data"), dict) else {}
    organization = _normalized_org(as_data.get("holder"))
    if organization == "Unknown" and local_maxmind:
        organization = str(local_maxmind.values.get("organization") or "Unknown")

    registry_geo = _registry_location(registry)
    ripe_geo = _first_location(geo or {})
    maxmind_values = _merge_location(local_geo, _merge_location(ripe_geo, registry_geo))
    maxmind = SourceData("Available", maxmind_values) if maxmind_values else SourceData("Unavailable")

    if token:
        if info:
            info_geo = {
                "country": info.get("country"),
                "country_name": info.get("country_name"),
                "city": info.get("city"),
                "region": info.get("region"),
                "coordinates": info.get("loc"),
            }
            ipinfo = SourceData("Available", _merge_location(info_geo, registry_geo))
            anycast = info.get("is_anycast") is True or info.get("anycast") is True
        else:
            ipinfo = SourceData("Unavailable", registry_geo)
            anycast = False
    else:
        ipinfo = SourceData("Not configured")
        anycast = False

    rdap_ip = rdap_ip if isinstance(rdap_ip, dict) else None
    rdap_as = rdap_as if isinstance(rdap_as, dict) else None
    registry_connection = registry.get("connection") if isinstance(registry, dict) and isinstance(registry.get("connection"), dict) else {}
    info_asn = info.get("asn") if isinstance(info, dict) and isinstance(info.get("asn"), dict) else {}
    info_company = info.get("company") if isinstance(info, dict) and isinstance(info.get("company"), dict) else {}
    if rdap_ip:
        as_organization = _vcard_org(rdap_as or {}) or organization
        website = _domain_website(
            registry_connection.get("domain"),
            info_asn.get("domain"),
            info_company.get("domain"),
        )
        registration = Registration(
            rir=_rir_from_rdap(rdap_ip),
            network_name=rdap_ip.get("name") or "Unknown",
            country=rdap_ip.get("country") or "Unknown",
            address_range=" - ".join(filter(None, (rdap_ip.get("startAddress"), rdap_ip.get("endAddress")))) or "Unknown",
            as_name=(rdap_as or {}).get("name") or "Unknown",
            as_country=(rdap_as or {}).get("country") or "Unknown",
            organization=as_organization,
            website=website,
        )
    else:
        registration = Registration(status="Unavailable")

    if registry_key:
        if registry:
            security = registry.get("security") if isinstance(registry.get("security"), dict) else {}
            privacy = SourceData(
                "Available",
                {
                    "proxy": security.get("is_proxy"),
                    "abuser": security.get("is_abuser"),
                    "server": security.get("is_cloud_provider"),
                },
            )
        else:
            privacy = SourceData("Unavailable")
    else:
        privacy = SourceData("Not configured")

    return IPResult(ip, prefix, asn, organization, anycast, maxmind, ipinfo, registration, privacy)


def country_flag(code: Any) -> str:
    code = str(code or "").upper()
    if len(code) != 2 or not code.isalpha():
        return "🏳"
    return "".join(chr(127397 + ord(character)) for character in code)


def country_name(code: Any, supplied: Any = None) -> str:
    if isinstance(supplied, str) and supplied and supplied != "?":
        return supplied
    code = str(code or "").upper()
    try:
        import pycountry

        country = pycountry.countries.get(alpha_2=code)
        if country:
            return country.name
    except ImportError:
        pass
    return COUNTRY_NAME_FALLBACK.get(code, "Unknown")


def registrable_domain(host: str) -> str:
    labels = host.rstrip(".").split(".")
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in COMMON_SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def service_links(ip: str, prefix: str) -> str:
    encoded_ip = quote(ip, safe="")
    encoded_prefix = quote(prefix, safe="/")
    links = (
        ("BGP", f"https://bgp.tools/prefix/{encoded_prefix}"),
        ("Censys", f"https://platform.censys.io/hosts/{encoded_ip}"),
        ("IPinfo", f"https://ipinfo.io/{encoded_ip}"),
        ("IPQS", f"https://www.ipqualityscore.com/free-ip-lookup-proxy-vpn-test/lookup/{encoded_ip}"),
        ("More", f"https://ipregion.xyz/{encoded_ip}"),
    )
    return " | ".join(f'<a href="{url}">{label}</a>' for label, url in links)


def _value(value: Any, default="Unknown") -> str:
    text = str(default if value in (None, "") else value)[:TEXT_LIMIT]
    return html.escape(text, quote=True)


def _asn_line(result: IPResult) -> str:
    asn = f"AS{result.asn}" if result.asn else "Unknown"
    return f"{asn} / {_value(result.organization)}"


def _geo_line(source: SourceData) -> str:
    if source.status != "Available":
        return _value(source.status)
    code = str(source.values.get("country") or "").upper()
    if len(code) != 2 or not code.isalpha() or code == "?":
        return "🏳 No geo data"
    name = country_name(code, source.values.get("country_name"))
    location = [f"{country_flag(code)} {code} {name}"]
    location.extend(str(source.values[key]) for key in ("region", "city") if source.values.get(key))
    return _value(", ".join(location))


def _registration_lines(result: IPResult) -> list[str]:
    registration = result.registration
    if registration.status != "Available":
        return [f"▢ Registration ({_value(registration.rir)}):", _value(registration.status)]
    ip_code = str(registration.country).upper()
    as_code = str(registration.as_country).upper()
    as_name = _value(registration.as_name)
    if registration.website:
        as_name = f'<a href="{_value(registration.website)}">{as_name}</a>'
    return [
        f"▢ Registration ({_value(registration.rir)}):",
        f"{country_flag(ip_code)} {_value(ip_code)} {_value(country_name(ip_code))} (IP)",
        _value(registration.network_name),
        f"{country_flag(as_code)} {_value(as_code)} {_value(country_name(as_code))} (AS)",
        f"{as_name} / {_value(registration.organization)}",
    ]


def _privacy_value(value: Any) -> str:
    return "✅" if value is True else "❌" if value is False else "?"


def _group_parts(group: list[IPResult], host: str | None = None) -> list[str]:
    result = group[0]
    parts = []
    if host:
        domain = quote(registrable_domain(host), safe="")
        parts.append(f'🔗 Host: {_value(host)} (<a href="https://info.addr.tools/{domain}">Whois</a>?)')
        parts.append(SEPARATOR)
    for item in group:
        anycast = " is anycast 🚀" if item.anycast else ""
        parts.append(f"IP: {_value(item.ip)}{anycast}\n{service_links(item.ip, item.prefix)}")
    parts.append(SEPARATOR)
    parts.append(f"▢ MaxMind:\n{_geo_line(result.maxmind)}\n{_asn_line(result)}")
    parts.append(f"▢ IPinfo & Cloudflare:\n{_geo_line(result.ipinfo)}\n{_asn_line(result)}")
    parts.append("\n".join(_registration_lines(result)))
    privacy = result.privacy
    if privacy.status == "Available":
        privacy_line = " | ".join(
            (
                f"Proxy {_privacy_value(privacy.values.get('proxy'))}",
                f"Abuser {_privacy_value(privacy.values.get('abuser'))}",
                f"Server {_privacy_value(privacy.values.get('server'))}",
            )
        )
    else:
        privacy_line = _value(privacy.status)
    parts.append(f"▢ Privacy info (ipregistry․co):\n{privacy_line}")
    return parts


def _signature(result: IPResult) -> str:
    data = {
        "prefix": result.prefix,
        "asn": result.asn,
        "organization": result.organization,
        "anycast": result.anycast,
        "maxmind": (result.maxmind.status, result.maxmind.values),
        "ipinfo": (result.ipinfo.status, result.ipinfo.values),
        "registration": result.registration.__dict__,
        "privacy": (result.privacy.status, result.privacy.values),
    }
    return json.dumps(data, sort_keys=True, default=str)


def group_results(results: list[IPResult]) -> list[list[IPResult]]:
    groups = []
    indexes = {}
    for result in results:
        signature = _signature(result)
        if signature not in indexes:
            indexes[signature] = len(groups)
            groups.append([])
        groups[indexes[signature]].append(result)
    return groups


def format_group(group: list[IPResult], host: str | None = None) -> str:
    parts = _group_parts(group, host)
    header_count = (2 if host else 0) + len(group) + 1
    return "\n".join(parts[:header_count]) + "\n" + "\n\n".join(parts[header_count:])


def _append_piece(chunks: list[str], current: str, piece: str, limit: int, separator: str) -> str:
    separator = separator if current else ""
    if len(current) + len(separator) + len(piece) <= limit:
        return current + separator + piece
    if current:
        chunks.append(current)
        current = ""
    if len(piece) <= limit:
        return piece
    lines = piece.splitlines()
    for line in lines:
        line_separator = "\n" if current else ""
        if len(current) + len(line_separator) + len(line) <= limit:
            current += line_separator + line
        else:
            if current:
                chunks.append(current)
            current = line
    return current


def render_chunks(results: list[IPResult], host: str | None = None, limit: int = 4096) -> list[str]:
    chunks = []
    current = ""
    for group_index, group in enumerate(group_results(results)):
        group_host = host if group_index == 0 else None
        parts = _group_parts(group, group_host)
        header_count = (2 if group_host else 0) + len(group) + 1
        for index, piece in enumerate(parts):
            if group_index and index == 0:
                separator = "\n\n"
            elif index <= header_count:
                separator = "\n"
            else:
                separator = "\n\n"
            current = _append_piece(chunks, current, piece, limit, separator)
    if current:
        chunks.append(current)
    return chunks
