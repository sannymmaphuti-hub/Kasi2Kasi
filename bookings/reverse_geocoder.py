import hashlib
import json
import os
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.cache import cache


DEFAULT_GEOCODING_URL = "https://nominatim.openstreetmap.org/reverse"
CACHE_TIMEOUT_SECONDS = 60 * 60 * 24 * 30
NETWORK_TIMEOUT_SECONDS = 4


def _validated_coordinate(value, minimum, maximum):
    if isinstance(value, bool) or value is None:
        raise ValueError("Invalid coordinate.")

    try:
        coordinate = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid coordinate.") from None

    if not coordinate.is_finite() or not minimum <= coordinate <= maximum:
        raise ValueError("Coordinate is outside the permitted range.")

    return coordinate


def reverse_geocode(latitude, longitude):
    """Return a readable address, or None when unavailable."""
    latitude = _validated_coordinate(latitude, Decimal("-90"), Decimal("90"))
    longitude = _validated_coordinate(longitude, Decimal("-180"), Decimal("180"))

    lat_text = f"{latitude:.6f}"
    lon_text = f"{longitude:.6f}"

    cache_material = f"{lat_text},{lon_text}"
    cache_key = "k2k:reverse-geocode:" + hashlib.sha256(
        cache_material.encode("utf-8")
    ).hexdigest()

    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None

    base_url = os.environ.get(
        "KASI2KASI_GEOCODING_URL",
        DEFAULT_GEOCODING_URL,
    ).strip()

    contact = os.environ.get("KASI2KASI_GEOCODING_CONTACT", "").strip()
    user_agent = "Kasi2Kasi/0.5"
    if contact:
        user_agent += f" ({contact})"

    query = urlencode({
        "format": "jsonv2",
        "lat": lat_text,
        "lon": lon_text,
        "addressdetails": 1,
        "zoom": 18,
    })

    separator = "&" if "?" in base_url else "?"
    request = Request(
        f"{base_url}{separator}{query}",
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if not isinstance(payload, dict):
            return None

        address = payload.get("display_name")
        if not isinstance(address, str) or not address.strip():
            cache.set(cache_key, "", timeout=300)
            return None

        result = {
            "address": address.strip(),
            "provider": "OpenStreetMap Nominatim",
            "attribution": "┬⌐ OpenStreetMap contributors",
        }
        cache.set(cache_key, result, timeout=CACHE_TIMEOUT_SECONDS)
        return result

    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ):
        return None
