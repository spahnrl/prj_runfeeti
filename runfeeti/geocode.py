from __future__ import annotations

import re
from dataclasses import dataclass

from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from geopy.location import Location


@dataclass(frozen=True)
class Geocoded:
    """Result of resolving a free-text address via Nominatim."""

    address: str
    latitude: float
    longitude: float
    display_name: str
    resolved_query: str
    note: str | None = None


# Common cases where USPS/local usage differs from OpenStreetMap naming.
_STREET_SUFFIX_SWAPS: tuple[tuple[str, str], ...] = (
    (" Lane", " Drive"),
    (" lane", " Drive"),
    (" LN", " Drive"),
    (" Ln", " Drive"),
    (" Drive", " Lane"),
    (" drive", " Lane"),
    (" Street", " St"),
    (" street", " St"),
    (" Avenue", " Ave"),
    (" avenue", " Ave"),
    (" Boulevard", " Blvd"),
    (" Road", " Rd"),
    (" road", " Rd"),
)

_ZIP_TAIL = re.compile(r",?\s*\b\d{5}(?:-\d{4})?\s*$", re.IGNORECASE)


def _collapse_ws(s: str) -> str:
    return " ".join(s.split()).strip()


def _split_street_and_rest(normalized: str) -> tuple[str | None, str | None]:
    if "," not in normalized:
        return None, None
    parts = [p.strip() for p in normalized.split(",")]
    street = parts[0]
    rest = ", ".join(parts[1:]).strip()
    return street, rest if rest else None


def _queries_to_try(address: str) -> list[str]:
    """Ordered unique lookup strings: normalized input plus helpful variants."""
    n = _collapse_ws(address)
    if not n:
        return []

    seen: set[str] = set()
    out: list[str] = []

    def add(q: str) -> None:
        q = _collapse_ws(q)
        if q and q not in seen:
            seen.add(q)
            out.append(q)

    add(n)

    street, rest = _split_street_and_rest(n)
    if street and rest:
        for old, new in _STREET_SUFFIX_SWAPS:
            if old in street:
                ns = street.replace(old, new)
                if ns != street:
                    add(f"{ns}, {rest}")

        rest_no_zip = _ZIP_TAIL.sub("", rest).strip().rstrip(",").strip()
        if rest_no_zip and rest_no_zip != rest:
            add(f"{street}, {rest_no_zip}")
            for old, new in _STREET_SUFFIX_SWAPS:
                if old in street:
                    ns = street.replace(old, new)
                    if ns != street:
                        add(f"{ns}, {rest_no_zip}")

    return out


def geocode_address(address: str, *, user_agent: str = "runfeeti/0.1") -> Geocoded:
    locator = Nominatim(user_agent=user_agent)
    original = _collapse_ws(address)
    if not original:
        raise ValueError("Address is empty.")

    last_error: str | None = None
    for q in _queries_to_try(original):
        loc: Location | None = None
        try:
            loc = locator.geocode(q, language="en", timeout=30)
        except (GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable, OSError) as exc:
            last_error = str(exc)
            continue
        if loc is None:
            continue

        note: str | None = None
        if q != original:
            note = (
                "Lookup succeeded using an alternate spelling (OpenStreetMap often differs "
                f"from mail labels, e.g. Lane vs Drive). Tried: {q!r}."
            )

        return Geocoded(
            address=original,
            latitude=float(loc.latitude),
            longitude=float(loc.longitude),
            display_name=str(loc.address or q),
            resolved_query=q,
            note=note,
        )

    hint = (
        " Nominatim could not find that exact string. Try the street name as it appears on "
        "OpenStreetMap (for this area, house numbers on Haggans are listed as Haggans Drive, "
        "ZIP 78737 in OSM, even if your mail says Lane or 78739)."
    )
    if last_error:
        raise ValueError(f"Could not geocode address: {original!r}. ({last_error}){hint}")
    raise ValueError(f"Could not geocode address: {original!r}.{hint}")


def _label_from_nominatim_raw(raw: dict) -> str:
    """Build a short 'number + street' style label from a Nominatim reverse payload."""
    addr = raw.get("address") or {}
    hn = addr.get("house_number")
    road = (
        addr.get("road")
        or addr.get("pedestrian")
        or addr.get("footway")
        or addr.get("path")
        or addr.get("residential")
        or addr.get("neighbourhood")
    )
    parts: list[str] = []
    if hn:
        parts.append(str(hn).strip())
    if road:
        parts.append(str(road).strip())
    if parts:
        return " ".join(parts)
    disp = str(raw.get("display_name") or "").strip()
    if disp:
        return disp.split(",")[0].strip()
    return ""


def lookup_corner_labels(
    latlons: list[tuple[float, float]],
    *,
    user_agent: str = "runfeeti/0.1",
    min_delay_s: float = 1.05,
) -> list[str]:
    """
    Reverse-geocode many points with caching and polite rate limiting (Nominatim).
    Order matches input; duplicate rounded coordinates reuse one request.
    """
    from geopy.extra.rate_limiter import RateLimiter

    if not latlons:
        return []

    locator = Nominatim(user_agent=user_agent)
    reverse = RateLimiter(locator.reverse, min_delay_seconds=min_delay_s)

    cache: dict[tuple[float, float], str] = {}
    out: list[str] = []

    def one(lat: float, lon: float) -> str:
        key = (round(lat, 5), round(lon, 5))
        if key in cache:
            return cache[key]
        label = ""
        try:
            loc = reverse(f"{lat}, {lon}", language="en", exactly_one=True, timeout=30)
            if loc and loc.raw:
                label = _label_from_nominatim_raw(loc.raw)
        except (GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable, OSError):
            pass
        if not label:
            label = f"{lat:.5f}, {lon:.5f}"
        cache[key] = label
        return label

    for lat, lon in latlons:
        out.append(one(lat, lon))
    return out
