from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from accounts.models import UserProfile
from bookings.models import DriverLiveLocation, TransportRequest


TRACKABLE_STATUSES = {
    TransportRequest.Status.ACCEPTED,
    TransportRequest.Status.CONFIRMED,
}
LOCATION_MAX_AGE = timedelta(seconds=90)


@login_required
@require_GET
def customer_ride_location_api(request, ride_id):
    """Return a fresh shared driver position only to the ride's customer."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return JsonResponse({"error": "Account profile required."}, status=403)

    if profile.role != UserProfile.Role.CUSTOMER:
        return JsonResponse({"error": "Customer access required."}, status=403)

    ride = get_object_or_404(
        TransportRequest,
        pk=ride_id,
        customer=request.user,
    )

    if ride.status not in TRACKABLE_STATUSES:
        return JsonResponse(
            {"sharing": False, "available": False,
             "message": "Live tracking is available only for accepted or confirmed rides."},
            status=200,
        )

    try:
        location = DriverLiveLocation.objects.get(
            ride=ride,
            driver=ride.assigned_driver,
            is_sharing=True,
        )
    except (DriverLiveLocation.DoesNotExist, DriverLiveLocation.MultipleObjectsReturned):
        return JsonResponse(
            {"sharing": False, "available": False,
             "message": "The driver is not currently sharing their location."},
            status=200,
        )

    now = timezone.now()

    if (
        location.latitude is None
        or location.longitude is None
        or location.updated_at < now - LOCATION_MAX_AGE
        or location.updated_at > now + timedelta(seconds=10)
    ):
        return JsonResponse(
            {"sharing": True, "available": False,
             "message": "The driver's location is waiting for a fresh GPS update."},
            status=200,
        )

    return JsonResponse({
        "sharing": True,
        "available": True,
        "latitude": str(location.latitude),
        "longitude": str(location.longitude),
        "updated_at": location.updated_at.isoformat(),
    })


@login_required
def customer_ride_tracking_page(request, ride_id):
    """Render live tracking for the authenticated owner of an eligible ride."""
    from django.shortcuts import render

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return JsonResponse({"error": "Account profile required."}, status=403)

    if profile.role != UserProfile.Role.CUSTOMER:
        return JsonResponse({"error": "Customer access required."}, status=403)

    ride = get_object_or_404(
        TransportRequest,
        pk=ride_id,
        customer=request.user,
    )

    if ride.status not in TRACKABLE_STATUSES:
        from django.contrib import messages
        from django.shortcuts import redirect

        messages.info(
            request,
            "Live tracking is available for accepted or confirmed rides.",
        )
        return redirect("my_rides")

    return render(
        request,
        "accounts/customer_ride_tracking.html",
        {
            "ride": ride,
            "location_api_url": reverse(
                "customer_ride_location_api",
                kwargs={"ride_id": ride.pk},
            ),
        },
    )
