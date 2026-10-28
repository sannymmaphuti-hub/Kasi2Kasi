from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .fare_engine import FareCalculationError, calculate_fare
import json
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.models import UserProfile
from .forms import TransportRequestForm
from .models import TransportRequest
from .journey_estimator import JourneyEstimationError, estimate_journey
from .reverse_geocoder import reverse_geocode


def _calculate_booking_estimated_fare(booking):
    """Return a server-calculated estimate, or None if unavailable."""
    coordinates = {
        "pickup_latitude": booking.pickup_latitude,
        "pickup_longitude": booking.pickup_longitude,
        "destination_latitude": booking.destination_latitude,
        "destination_longitude": booking.destination_longitude,
    }

    # Manual location entry remains supported.
    if any(value is None for value in coordinates.values()):
        return None

    pricing_names = (
        "KASI2KASI_BASE_FARE",
        "KASI2KASI_RATE_PER_KM",
        "KASI2KASI_RATE_PER_MINUTE",
    )
    pricing_values = {
        name: getattr(settings, name, None)
        for name in pricing_names
    }

    # Never invent rates or calculate a fare from incomplete configuration.
    if not all(
        value is not None and str(value).strip() != ""
        for value in pricing_values.values()
    ):
        return None

    try:
        estimate = estimate_journey(**coordinates, timeout_seconds=5)

        fare = calculate_fare(
            base_fare=pricing_values["KASI2KASI_BASE_FARE"],
            distance_km=estimate.distance_km,
            rate_per_km=pricing_values["KASI2KASI_RATE_PER_KM"],
            estimated_minutes=estimate.duration_minutes,
            rate_per_minute=pricing_values["KASI2KASI_RATE_PER_MINUTE"],
            currency="ZAR",
        )

        return fare.total
    except (
        JourneyEstimationError,
        FareCalculationError,
        TypeError,
        ValueError,
        InvalidOperation,
    ):
        # Expected estimation or pricing failures must not block a valid
        # booking. Unexpected programming errors should remain visible.
        return None

def home(request):
    return render(request, "home.html")


@login_required
@require_POST
def journey_estimate_api(request):
    """Return an indicative road estimate without changing any booking."""
    if not UserProfile.objects.filter(
        user=request.user,
        role=UserProfile.Role.CUSTOMER,
    ).exists():
        return JsonResponse(
            {"error": "Only customer accounts can request journey estimates."},
            status=403,
        )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "A valid JSON request is required."}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "The request must be a JSON object."}, status=400)

    coordinate_names = (
        "pickup_latitude",
        "pickup_longitude",
        "destination_latitude",
        "destination_longitude",
    )
    coordinates = {}

    for name in coordinate_names:
        value = payload.get(name)

        # Booleans are technically integers in Python, but are not coordinates.
        if isinstance(value, bool) or value is None:
            return JsonResponse(
                {"error": f"Valid {name} is required."},
                status=400,
            )

        try:
            coordinate = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return JsonResponse(
                {"error": f"Valid {name} is required."},
                status=400,
            )

        if not coordinate.is_finite():
            return JsonResponse(
                {"error": f"Valid {name} is required."},
                status=400,
            )

        if name.endswith("latitude") and not Decimal("-90") <= coordinate <= Decimal("90"):
            return JsonResponse(
                {"error": f"{name} must be between -90 and 90."},
                status=400,
            )

        if name.endswith("longitude") and not Decimal("-180") <= coordinate <= Decimal("180"):
            return JsonResponse(
                {"error": f"{name} must be between -180 and 180."},
                status=400,
            )

        coordinates[name] = coordinate

    pickup = (
        coordinates["pickup_latitude"],
        coordinates["pickup_longitude"],
    )
    destination = (
        coordinates["destination_latitude"],
        coordinates["destination_longitude"],
    )

    if pickup == destination:
        return JsonResponse(
            {"error": "Pickup and destination must be different points."},
            status=400,
        )

    try:
        estimate = estimate_journey(**coordinates)
    except JourneyEstimationError:
        return JsonResponse(
            {"error": "A road estimate is temporarily unavailable. Please try again."},
            status=503,
        )

    response_data = {
        "distance_km": str(estimate.distance_km),
        "duration_minutes": str(estimate.duration_minutes),
        "provider": estimate.provider,
        "route_coordinates": [
            list(point)
            for point in getattr(estimate, "route_coordinates", ())
        ],
        "indicative": True,
    }

    # Never invent pricing values. Rates must be explicitly configured.
    pricing_names = (
        "KASI2KASI_BASE_FARE",
        "KASI2KASI_RATE_PER_KM",
        "KASI2KASI_RATE_PER_MINUTE",
    )
    pricing_values = {
        name: getattr(settings, name, None)
        for name in pricing_names
    }

    if all(value is not None and str(value).strip() != ""
           for value in pricing_values.values()):
        try:
            fare = calculate_fare(
                base_fare=pricing_values["KASI2KASI_BASE_FARE"],
                distance_km=estimate.distance_km,
                rate_per_km=pricing_values["KASI2KASI_RATE_PER_KM"],
                estimated_minutes=estimate.duration_minutes,
                rate_per_minute=pricing_values["KASI2KASI_RATE_PER_MINUTE"],
                currency="ZAR",
            )

            response_data["fare"] = {
                "available": True,
                "currency": fare.currency,
                "base_fare": str(fare.base_fare),
                "distance_charge": str(fare.distance_charge),
                "time_charge": str(fare.time_charge),
                "after_hours_charge": str(fare.after_hours_charge),
                "other_adjustments": str(fare.other_adjustments),
                "discount": str(fare.discount),
                "total": str(fare.total),
                "indicative": True,
            }
        except (FareCalculationError, TypeError, ValueError):
            response_data["fare"] = {
                "available": False,
                "reason": "pricing_configuration_invalid",
            }
    else:
        response_data["fare"] = {
            "available": False,
            "reason": "pricing_not_configured",
        }

    return JsonResponse(response_data)


@login_required
@require_POST
def reverse_geocode_api(request):
    # Resolve a customer's selected map coordinates to a readable place.
    if not UserProfile.objects.filter(
        user=request.user,
        role=UserProfile.Role.CUSTOMER,
    ).exists():
        return JsonResponse({"error": "Customer access required."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "A JSON object is required."}, status=400)

    coordinates = {}
    for key, minimum, maximum in (
        ("latitude", Decimal("-90"), Decimal("90")),
        ("longitude", Decimal("-180"), Decimal("180")),
    ):
        value = payload.get(key)
        if isinstance(value, bool) or value is None:
            return JsonResponse({"error": f"Valid {key} is required."}, status=400)
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return JsonResponse({"error": f"Valid {key} is required."}, status=400)
        if not number.is_finite() or not minimum <= number <= maximum:
            return JsonResponse(
                {"error": f"{key} is outside the permitted range."},
                status=400,
            )
        coordinates[key] = number

    try:
        result = reverse_geocode(coordinates["latitude"], coordinates["longitude"])
    except Exception:
        # Geocoding is optional; provider failures must not break booking.
        result = None

    if not isinstance(result, dict):
        return JsonResponse({
            "address": None,
            "provider": None,
            "attribution": "© OpenStreetMap contributors",
        })

    address = result.get("address")
    if not isinstance(address, str) or not address.strip():
        address = None

    return JsonResponse({
        "address": address,
        "provider": result.get("provider"),
        "attribution": result.get("attribution", "© OpenStreetMap contributors"),
    })

@login_required
def request_ride(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(
            request,
            "Your account profile is missing. Please contact support.",
        )
        return redirect("account_dashboard")

    if profile.role != UserProfile.Role.CUSTOMER:
        messages.error(
            request,
            "Only customer accounts can request rides.",
        )
        return redirect("account_dashboard")

    if request.method == "POST":
        form = TransportRequestForm(request.POST)

        if form.is_valid():
            booking = form.save(commit=False)
            booking.customer = request.user
            booking.estimated_fare = _calculate_booking_estimated_fare(booking)
            booking.save()

            messages.success(
                request,
                "Your ride request has been received. "
                "We will contact you to discuss availability and pricing.",
            )
            return redirect("request_ride")
    else:
        form = TransportRequestForm(
            initial={
                "customer_name": (
                    request.user.get_full_name()
                    or request.user.username
                ),
            }
        )

    return render(
        request,
        "request_ride.html",
        {"form": form},
    )


@login_required
def my_rides(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(
            request,
            "Your account profile is missing. Please contact support.",
        )
        return redirect("account_dashboard")

    if profile.role != UserProfile.Role.CUSTOMER:
        messages.error(
            request,
            "Ride history is available to customer accounts only.",
        )
        return redirect("account_dashboard")

    rides = TransportRequest.objects.filter(
        customer=request.user
    ).order_by("-created_at")

    return render(
        request,
        "accounts/my_rides.html",
        {"rides": rides},
    )

@login_required
def confirm_ride_fare(request, ride_id):
    """Let a customer accept the proposed fare for their own ride."""
    from decimal import Decimal, InvalidOperation

    from django.db import transaction
    from django.http import HttpResponseNotAllowed
    from django.shortcuts import get_object_or_404

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(
            request,
            "Your account profile is missing. Please contact support.",
        )
        return redirect("account_dashboard")

    if profile.role != UserProfile.Role.CUSTOMER:
        messages.error(
            request,
            "Only customers can confirm their ride fare.",
        )
        return redirect("account_dashboard")

    with transaction.atomic():
        booking = get_object_or_404(
            TransportRequest.objects.select_for_update(),
            pk=ride_id,
            customer=request.user,
        )

        if booking.status != TransportRequest.Status.ACCEPTED:
            messages.error(
                request,
                "Only accepted rides can have their fare confirmed.",
            )
            return redirect("my_rides")

        if booking.proposed_fare is None:
            messages.error(
                request,
                "A proposed fare is not available for this ride yet.",
            )
            return redirect("my_rides")

        try:
            proposed_fare = Decimal(str(booking.proposed_fare))
        except (InvalidOperation, TypeError, ValueError):
            proposed_fare = Decimal("0")

        if not proposed_fare.is_finite() or proposed_fare <= 0:
            messages.error(
                request,
                "The proposed fare is invalid. Please contact support.",
            )
            return redirect("my_rides")

        booking.agreed_fare = proposed_fare
        booking.status = TransportRequest.Status.CONFIRMED
        booking.save(update_fields=["agreed_fare", "status"])

    messages.success(
        request,
        "Fare confirmed. Your ride is now confirmed.",
    )
    return redirect("my_rides")

@login_required
def cancel_ride(request, ride_id):
    """Allow customers to cancel their own pending ride requests."""
    from django.db import transaction
    from django.http import HttpResponseNotAllowed
    from django.shortcuts import get_object_or_404

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(
            request,
            "Your account profile is missing. Please contact support.",
        )
        return redirect("account_dashboard")

    if profile.role != UserProfile.Role.CUSTOMER:
        messages.error(
            request,
            "Only customer accounts can cancel ride requests.",
        )
        return redirect("account_dashboard")

    with transaction.atomic():
        booking = get_object_or_404(
            TransportRequest.objects.select_for_update(),
            pk=ride_id,
            customer=request.user,
        )

        if booking.status != TransportRequest.Status.PENDING:
            messages.error(
                request,
                "Only pending ride requests can be cancelled.",
            )
            return redirect("my_rides")

        booking.status = TransportRequest.Status.CANCELLED
        booking.save(update_fields=["status"])

        from bookings.models import DriverLiveLocation
        DriverLiveLocation.objects.filter(ride=booking).update(
            is_sharing=False,
            latitude=None,
            longitude=None,
        )

    messages.success(
        request,
        "Your ride request has been cancelled.",
    )
    return redirect("my_rides")


