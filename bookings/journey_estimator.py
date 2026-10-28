"""Independent road-journey estimation using an OSRM-compatible service."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_ROUTING_URL = "https://router.project-osrm.org/route/v1/driving"
DEFAULT_TIMEOUT_SECONDS = 20
MAX_COORDINATE_DECIMALS = Decimal("0.000001")


class JourneyEstimationError(ValueError):
    """Raised when a road journey cannot be estimated safely."""


@dataclass(frozen=True)
class JourneyEstimate:
    """Road distance, estimated duration, and optional route geometry."""

    distance_km: Decimal
    duration_minutes: Decimal
    provider: str
    route_coordinates: tuple = ()


def _coordinate(value, field_name, minimum, maximum):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise JourneyEstimationError(
            f"{field_name} must be a valid coordinate."
        ) from exc

    if not number.is_finite():
        raise JourneyEstimationError(f"{field_name} must be finite.")

    if not Decimal(str(minimum)) <= number <= Decimal(str(maximum)):
        raise JourneyEstimationError(
            f"{field_name} is outside its valid range."
        )

    return number.quantize(MAX_COORDINATE_DECIMALS)


def _positive_finite_decimal(value, field_name):
    if isinstance(value, bool):
        raise JourneyEstimationError(f"{field_name} must be a valid number.")

    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise JourneyEstimationError(
            f"{field_name} must be a valid number."
        ) from exc

    if not number.is_finite() or number <= 0:
        raise JourneyEstimationError(
            f"{field_name} must be finite and greater than zero."
        )

    return number


def _positive_finite_number(value, field_name):
    number = _positive_finite_decimal(value, field_name)
    try:
        return float(number)
    except (OverflowError, ValueError) as exc:
        raise JourneyEstimationError(
            f"{field_name} must be a valid number."
        ) from exc


def estimate_journey(
    *,
    pickup_latitude,
    pickup_longitude,
    destination_latitude,
    destination_longitude,
    routing_url=DEFAULT_ROUTING_URL,
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    http_get=None,
):
    """Estimate a driving route without changing any booking.

    Coordinates are supplied as latitude/longitude, while OSRM expects
    longitude,latitude in its route URL.

    http_get is an optional injectable function accepting (url, timeout)
    and returning decoded JSON. It is intended for deterministic tests.
    """
    pickup_lat = _coordinate(
        pickup_latitude, "pickup_latitude", -90, 90
    )
    pickup_lon = _coordinate(
        pickup_longitude, "pickup_longitude", -180, 180
    )
    destination_lat = _coordinate(
        destination_latitude, "destination_latitude", -90, 90
    )
    destination_lon = _coordinate(
        destination_longitude, "destination_longitude", -180, 180
    )

    if pickup_lat == destination_lat and pickup_lon == destination_lon:
        raise JourneyEstimationError(
            "Pickup and destination coordinates must be different."
        )

    timeout = _positive_finite_number(timeout_seconds, "timeout_seconds")

    if not isinstance(routing_url, str):
        raise JourneyEstimationError("routing_url must be a string.")

    routing_url = routing_url.strip().rstrip("/")

    if not routing_url.startswith("https://"):
        raise JourneyEstimationError(
            "The routing service must use HTTPS."
        )

    coordinates = (
        f"{pickup_lon},{pickup_lat};"
        f"{destination_lon},{destination_lat}"
    )
    url = f"{routing_url}/{quote(coordinates, safe=',;')}?overview=full&geometries=geojson"

    if http_get is None:
        def http_get(request_url, request_timeout):
            request = Request(
                request_url,
                headers={"User-Agent": "Kasi2Kasi-JourneyEstimator/0.1"},
            )
            with urlopen(request, timeout=request_timeout) as response:
                if response.status != 200:
                    raise JourneyEstimationError(
                        "The routing service returned an unsuccessful response."
                    )
                return json.loads(response.read().decode("utf-8"))

    try:
        payload = http_get(url, timeout)
    except JourneyEstimationError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise JourneyEstimationError(
            "The routing service could not provide a journey estimate."
        ) from exc
    except Exception as exc:
        raise JourneyEstimationError(
            "The routing request failed unexpectedly."
        ) from exc

    if not isinstance(payload, dict):
        raise JourneyEstimationError(
            "The routing service returned an invalid response."
        )

    if payload.get("code") != "Ok":
        raise JourneyEstimationError(
            "No usable road route was returned by the routing service."
        )

    routes = payload.get("routes")

    if not isinstance(routes, list) or not routes:
        raise JourneyEstimationError(
            "The routing service returned no routes."
        )

    route = routes[0]

    if not isinstance(route, dict):
        raise JourneyEstimationError(
            "The routing service returned invalid route data."
        )

    distance_meters = _positive_finite_decimal(
        route.get("distance"), "route distance"
    )
    duration_seconds = _positive_finite_decimal(
        route.get("duration"), "route duration"
    )

    distance_km = (
        distance_meters / Decimal("1000")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    duration_minutes = (
        duration_seconds / Decimal("60")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    if distance_km <= 0 or duration_minutes <= 0:
        raise JourneyEstimationError(
            "The route estimate is too small to use safely."
        )

    # Geometry is optional: a valid distance/time estimate remains useful
    # even if a routing provider omits or supplies unusable geometry.
    route_coordinates = ()
    geometry = route.get("geometry")

    if isinstance(geometry, dict):
        raw_coordinates = geometry.get("coordinates")

        if isinstance(raw_coordinates, list) and len(raw_coordinates) >= 2:
            validated_coordinates = []

            for point in raw_coordinates:
                if not isinstance(point, (list, tuple)) or len(point) < 2:
                    validated_coordinates = []
                    break

                longitude, latitude = point[0], point[1]

                if isinstance(longitude, bool) or isinstance(latitude, bool):
                    validated_coordinates = []
                    break

                try:
                    longitude = float(longitude)
                    latitude = float(latitude)
                except (TypeError, ValueError, OverflowError):
                    validated_coordinates = []
                    break

                if (
                    not math.isfinite(longitude)
                    or not math.isfinite(latitude)
                    or not -180 <= longitude <= 180
                    or not -90 <= latitude <= 90
                ):
                    validated_coordinates = []
                    break

                validated_coordinates.append((longitude, latitude))

            if len(validated_coordinates) >= 2:
                route_coordinates = tuple(validated_coordinates)

    return JourneyEstimate(
        distance_km=distance_km,
        duration_minutes=duration_minutes,
        provider="OSRM-compatible routing service",
        route_coordinates=route_coordinates,
    )
