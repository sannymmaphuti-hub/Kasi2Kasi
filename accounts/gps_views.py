import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from bookings.models import DriverLiveLocation, TransportRequest
from accounts.models import UserProfile


ACTIVE_LOCATION_STATUSES = {
    TransportRequest.Status.ACCEPTED,
    TransportRequest.Status.CONFIRMED,
}


def _decimal_coordinate(value, minimum, maximum):
    if value is None or isinstance(value, bool):
        raise ValueError("A valid coordinate is required.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Coordinates must be valid numbers.")
    if not number.is_finite() or number < minimum or number > maximum:
        raise ValueError("Coordinate is outside the permitted range.")
    return number.quantize(Decimal("0.000001"))


@login_required
@require_POST
def driver_location_api(request, ride_id):
    """Allow an approved assigned driver to start, update, or stop GPS sharing."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return JsonResponse({"error": "Account profile required."}, status=403)

    if (
        profile.role != UserProfile.Role.DRIVER
        or profile.driver_status != UserProfile.DriverStatus.APPROVED
    ):
        return JsonResponse({"error": "Approved driver access required."}, status=403)

    ride = get_object_or_404(
        TransportRequest,
        pk=ride_id,
        assigned_driver=request.user,
    )

    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "Invalid JSON body."}, status=400)
    else:
        payload = request.POST

    action = payload.get("action")
    if action not in {"start", "update", "stop"}:
        return JsonResponse(
            {"error": "Action must be start, update, or stop."},
            status=400,
        )

    # Stopping sharing must remain possible if a ride becomes inactive.
    if action != "stop" and ride.status not in ACTIVE_LOCATION_STATUSES:
        return JsonResponse(
            {"error": "GPS sharing is only available for accepted or confirmed rides."},
            status=409,
        )

    location, _ = DriverLiveLocation.objects.get_or_create(
        ride=ride,
        defaults={"driver": request.user},
    )

    # Do not silently transfer a location record to another driver.
    if location.driver_id != request.user.id:
        return JsonResponse({"error": "Location ownership mismatch."}, status=403)

    if action == "stop":
        location.is_sharing = False
        location.save(update_fields=["is_sharing", "updated_at"])
        return JsonResponse({"ok": True, "sharing": False})

    if action == "start":
        location.is_sharing = True
        location.latitude = None
        location.longitude = None
        location.save(
            update_fields=[
                "is_sharing",
                "latitude",
                "longitude",
                "updated_at",
            ]
        )
        return JsonResponse({"ok": True, "sharing": True})

    if not location.is_sharing:
        return JsonResponse(
            {"error": "Start GPS sharing before sending location updates."},
            status=409,
        )

    try:
        latitude = _decimal_coordinate(payload.get("latitude"), Decimal("-90"), Decimal("90"))
        longitude = _decimal_coordinate(payload.get("longitude"), Decimal("-180"), Decimal("180"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    location.latitude = latitude
    location.longitude = longitude
    location.save(update_fields=["latitude", "longitude", "updated_at"])

    return JsonResponse({
        "ok": True,
        "sharing": True,
        "latitude": str(location.latitude),
        "longitude": str(location.longitude),
        "updated_at": location.updated_at.isoformat(),
    })
