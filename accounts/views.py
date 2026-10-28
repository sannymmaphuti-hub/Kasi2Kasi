import os
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import DriverRegistrationForm, DriverVehicleUpdateForm, RegistrationForm
from .permissions import approved_driver_required
from bookings.models import TransportRequest
from .models import DriverVehicle, UserProfile


def register(request, role):
    if role not in (
        UserProfile.Role.CUSTOMER,
        UserProfile.Role.DRIVER,
    ):
        return redirect("home")

    if request.user.is_authenticated:
        return redirect("account_dashboard")

    form_class = (
        DriverRegistrationForm
        if role == UserProfile.Role.DRIVER
        else RegistrationForm
    )

    if request.method == "POST":
        form = form_class(request.POST)

        if form.is_valid():
            from django.db import transaction

            user = form.save(commit=False)

            with transaction.atomic():
                user.save()

                profile = UserProfile(
                    user=user,
                    role=role,
                )
                profile.save()

                if role == UserProfile.Role.DRIVER:
                    DriverVehicle.objects.create(
                        driver=user,
                        vehicle_type=form.cleaned_data["vehicle_type"],
                        make=form.cleaned_data["make"],
                        model=form.cleaned_data["model"],
                        year=form.cleaned_data.get("year"),
                        registration_number=form.cleaned_data[
                            "registration_number"
                        ],
                        passenger_capacity=form.cleaned_data[
                            "passenger_capacity"
                        ],
                        is_active=True,
                        verified=False,
                    )

            login(request, user)

            if role == UserProfile.Role.DRIVER:
                messages.success(
                    request,
                    "Your driver account has been created. "
                    "Your account and vehicle require administrative "
                    "approval before you can access driver opportunities.",
                )
            else:
                messages.success(
                    request,
                    "Your customer account has been created.",
                )

            return redirect("account_dashboard")
    else:
        form = form_class()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
            "role": role,
            "is_driver_registration": role == UserProfile.Role.DRIVER,
        },
    )

class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse("account_dashboard")



@login_required
def driver_vehicle_management(request, vehicle_id=None):
    """Let a driver view and update only their own registered vehicles."""
    from django.http import HttpResponseNotAllowed

    if vehicle_id is None and request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    if vehicle_id is not None and request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, "Your account profile is missing.")
        return redirect("account_dashboard")

    if profile.role != UserProfile.Role.DRIVER:
        messages.error(request, "Vehicle management is available to drivers only.")
        return redirect("account_dashboard")

    vehicles = DriverVehicle.objects.filter(driver=request.user)

    if vehicle_id is None:
        return render(
            request,
            "accounts/driver_vehicles.html",
            {"vehicles": vehicles},
        )

    vehicle = vehicles.filter(pk=vehicle_id).first()
    if vehicle is None:
        messages.error(request, "That vehicle was not found in your account.")
        return redirect("driver_vehicle_management")

    if request.method == "POST":
        form = DriverVehicleUpdateForm(request.POST, instance=vehicle)
        if form.is_valid():
            critical_fields = (
                "vehicle_type",
                "make",
                "model",
                "year",
                "registration_number",
                "passenger_capacity",
            )
            original_values = {
                field: getattr(DriverVehicle.objects.get(pk=vehicle.pk), field)
                for field in critical_fields
            }
            changed = any(
                original_values[field] != form.cleaned_data[field]
                for field in critical_fields
            )

            updated_vehicle = form.save(commit=False)
            if changed:
                updated_vehicle.verified = False

            updated_vehicle.save()
            if changed:
                messages.success(
                    request,
                    "Vehicle details updated. The vehicle is marked unverified "
                    "until an administrator reviews the changes.",
                )
            else:
                messages.success(request, "Vehicle details saved.")

            return redirect("driver_vehicle_management")
    else:
        form = DriverVehicleUpdateForm(instance=vehicle)

    return render(
        request,
        "accounts/driver_vehicle_edit.html",
        {"form": form, "vehicle": vehicle},
    )


@login_required
def toggle_vehicle_active(request, vehicle_id):
    """Allow a driver to activate or deactivate only their own vehicle."""
    from django.http import HttpResponseNotAllowed

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, "Your account profile is missing.")
        return redirect("account_dashboard")

    if profile.role != UserProfile.Role.DRIVER:
        messages.error(request, "Vehicle management is available to drivers only.")
        return redirect("account_dashboard")

    vehicle = DriverVehicle.objects.filter(
        pk=vehicle_id,
        driver=request.user,
    ).first()

    if vehicle is None:
        messages.error(request, "That vehicle was not found in your account.")
        return redirect("driver_vehicle_management")

    vehicle.is_active = not vehicle.is_active
    vehicle.save(update_fields=["is_active"])

    if vehicle.is_active:
        messages.success(request, "Vehicle activated. Its verification status is unchanged.")
    else:
        messages.success(request, "Vehicle deactivated. Its record and verification status are preserved.")

    return redirect("driver_vehicle_management")

def toggle_driver_availability(request):
    """Allow approved drivers to change availability using POST only."""
    from django.http import HttpResponseNotAllowed

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, "Your account profile is missing.")
        return redirect("account_dashboard")

    if (
        profile.role != UserProfile.Role.DRIVER
        or profile.driver_status != UserProfile.DriverStatus.APPROVED
    ):
        messages.error(
            request,
            "Only approved drivers can change availability.",
        )
        return redirect("account_dashboard")

    requested_state = request.POST.get("available")

    if requested_state not in ("on", "off"):
        messages.error(request, "Invalid availability selection.")
        return redirect("account_dashboard")

    profile.is_available = requested_state == "on"
    profile.save(update_fields=["is_available"])

    if profile.is_available:
        messages.success(
            request,
            "You are online and available for new ride assignments.",
        )
    else:
        messages.success(
            request,
            "You are offline. Existing assigned rides remain unchanged.",
        )

    return redirect("account_dashboard")

@login_required
def account_dashboard(request):

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(
            request,
            "Your account profile is missing. "
            "Please contact the administrator.",
        )
        return redirect("account_login")

    if profile.role == UserProfile.Role.DRIVER:
        context = {"profile": profile}

        if profile.driver_status == UserProfile.DriverStatus.APPROVED:
            from django.utils import timezone

            assigned_rides = TransportRequest.objects.filter(
                assigned_driver=request.user
            )

            context["dashboard_counts"] = {
                "assigned": assigned_rides.count(),
                "pending": assigned_rides.filter(
                    status=TransportRequest.Status.PENDING
                ).count(),
                "accepted": assigned_rides.filter(
                    status=TransportRequest.Status.ACCEPTED
                ).count(),
                "confirmed": assigned_rides.filter(
                    status=TransportRequest.Status.CONFIRMED
                ).count(),
                "completed": assigned_rides.filter(
                    status=TransportRequest.Status.COMPLETED
                ).count(),
            }

            context["dashboard_upcoming_rides"] = assigned_rides.filter(
                travel_datetime__gte=timezone.now(),
                status__in=(
                    TransportRequest.Status.PENDING,
                    TransportRequest.Status.ACCEPTED,
                    TransportRequest.Status.CONFIRMED,
                ),
            ).order_by("travel_datetime", "-created_at")[:3]

        return render(
            request,
            "accounts/driver_dashboard.html",
            context,
        )

    from django.utils import timezone

    customer_rides = TransportRequest.objects.filter(
        customer=request.user
    ).order_by("-created_at")

    customer_context = {
        "profile": profile,
        "customer_dashboard_counts": {
            "total": customer_rides.count(),
            "pending": customer_rides.filter(
                status=TransportRequest.Status.PENDING
            ).count(),
            "accepted": customer_rides.filter(
                status=TransportRequest.Status.ACCEPTED
            ).count(),
            "confirmed": customer_rides.filter(
                status=TransportRequest.Status.CONFIRMED
            ).count(),
            "completed": customer_rides.filter(
                status=TransportRequest.Status.COMPLETED
            ).count(),
            "cancelled": customer_rides.filter(
                status=TransportRequest.Status.CANCELLED
            ).count(),
        },
        "customer_dashboard_recent_rides": customer_rides[:3],
    }

    return render(
        request,
        "accounts/customer_dashboard.html",
        customer_context,
    )




from .forms import ProfilePictureForm



@approved_driver_required
def assigned_driver_rides(request):
    """Show assigned rides grouped by journey time and status."""
    from django.utils import timezone

    rides = list(
        TransportRequest.objects
        .filter(assigned_driver=request.user)
        .order_by("travel_datetime", "-created_at")
    )

    now = timezone.now()

    upcoming_rides = [
        ride for ride in rides
        if ride.travel_datetime >= now
        and ride.status not in (
            TransportRequest.Status.COMPLETED,
            TransportRequest.Status.CANCELLED,
        )
    ]

    past_rides = [
        ride for ride in rides
        if ride.travel_datetime < now
        and ride.status not in (
            TransportRequest.Status.COMPLETED,
            TransportRequest.Status.CANCELLED,
        )
    ]

    completed_rides = [
        ride for ride in rides
        if ride.status == TransportRequest.Status.COMPLETED
    ]

    cancelled_rides = [
        ride for ride in rides
        if ride.status == TransportRequest.Status.CANCELLED
    ]

    return render(
        request,
        "accounts/assigned_rides.html",
        {
            "rides": rides,
            "upcoming_rides": upcoming_rides,
            "past_rides": past_rides,
            "completed_rides": completed_rides,
            "cancelled_rides": cancelled_rides,
            "rides_count": len(rides),
            "now": now,
            "ride_sections": [
                ("Upcoming rides", upcoming_rides),
                ("Past rides", past_rides),
                ("Completed rides", completed_rides),
                ("Cancelled rides", cancelled_rides),
            ],
        },
    )


@approved_driver_required
def propose_assigned_ride_fare(request, ride_id):
    """Allow an approved driver to propose a fare for their assigned ride."""
    from decimal import Decimal, InvalidOperation
    from django.db import transaction
    from django.http import HttpResponseNotAllowed
    from django.shortcuts import get_object_or_404

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, "Your account profile is missing.")
        return redirect("account_dashboard")

    if (
        profile.role != UserProfile.Role.DRIVER
        or profile.driver_status != UserProfile.DriverStatus.APPROVED
    ):
        messages.error(request, "Only approved drivers can propose a ride fare.")
        return redirect("assigned_driver_rides")

    raw_fare = request.POST.get("proposed_fare", "").strip()
    try:
        fare = Decimal(raw_fare)
    except (InvalidOperation, TypeError, ValueError):
        fare = None

    if fare is None or not fare.is_finite() or fare <= 0:
        messages.error(request, "Enter a valid fare greater than zero.")
        return redirect("assigned_driver_rides")

    with transaction.atomic():
        ride = get_object_or_404(
            TransportRequest.objects.select_for_update(),
            pk=ride_id,
            assigned_driver=request.user,
        )

        if ride.status != TransportRequest.Status.PENDING:
            messages.error(
                request,
                "A fare can only be proposed for a pending ride.",
            )
            return redirect("assigned_driver_rides")

        ride.proposed_fare = fare
        ride.save(update_fields=["proposed_fare"])

    messages.success(
        request,
        "Fare proposed successfully. You can now accept the ride.",
    )
    return redirect("assigned_driver_rides")


@approved_driver_required
def accept_assigned_ride(request, ride_id):
    """Allow an approved driver to accept their own pending ride."""
    from django.db import transaction
    from django.http import HttpResponseNotAllowed
    from django.shortcuts import get_object_or_404

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, "Your account profile is missing.")
        return redirect("account_dashboard")

    if (
        profile.role != UserProfile.Role.DRIVER
        or profile.driver_status != UserProfile.DriverStatus.APPROVED
    ):
        messages.error(request, "Only approved drivers can accept rides.")
        return redirect("assigned_driver_rides")

    with transaction.atomic():
        ride = get_object_or_404(
            TransportRequest.objects.select_for_update(),
            pk=ride_id,
            assigned_driver=request.user,
        )

        if ride.status != TransportRequest.Status.PENDING:
            messages.error(
                request,
                "Only pending rides can be accepted.",
            )
            return redirect("assigned_driver_rides")

        fare = ride.proposed_fare
        if fare is None or fare <= 0:
            messages.error(
                request,
                "Propose a valid fare before accepting this ride.",
            )
            return redirect("assigned_driver_rides")

        ride.status = TransportRequest.Status.ACCEPTED
        ride.save(update_fields=["status"])

    messages.success(
        request,
        "Ride accepted. Await customer confirmation of the fare.",
    )
    return redirect("assigned_driver_rides")

@login_required
def profile_settings(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(
            request,
            "Your account profile is missing. Please contact support.",
        )
        return redirect("account_dashboard")

    if request.method == "POST":
        form = ProfilePictureForm(
            request.POST,
            request.FILES,
            instance=profile,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile picture was updated.")
            return redirect("profile_settings")
    else:
        form = ProfilePictureForm(instance=profile)

    return render(
        request,
        "accounts/profile_settings.html",
        {
            "form": form,
            "profile": profile,
        },
    )

@approved_driver_required
def complete_assigned_ride(request, ride_id):
    """Allow approved drivers to complete their own confirmed rides."""
    from django.db import transaction
    from django.http import HttpResponseNotAllowed
    from django.shortcuts import get_object_or_404
    from django.utils import timezone

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, "Your account profile is missing.")
        return redirect("account_dashboard")

    if (
        profile.role != UserProfile.Role.DRIVER
        or profile.driver_status != UserProfile.DriverStatus.APPROVED
    ):
        messages.error(
            request,
            "Only approved drivers can complete assigned rides.",
        )
        return redirect("account_dashboard")

    with transaction.atomic():
        ride = get_object_or_404(
            TransportRequest.objects.select_for_update(),
            pk=ride_id,
            assigned_driver=request.user,
        )

        if ride.status != TransportRequest.Status.CONFIRMED:
            messages.error(
                request,
                "Only confirmed rides can be completed.",
            )
            return redirect("assigned_driver_rides")

        if ride.travel_datetime > timezone.now():
            messages.error(
                request,
                "A ride cannot be completed before its scheduled travel time.",
            )
            return redirect("assigned_driver_rides")

        ride.status = TransportRequest.Status.COMPLETED
        ride.save(update_fields=["status"])

        from bookings.models import DriverLiveLocation
        DriverLiveLocation.objects.filter(ride=ride).update(
            is_sharing=False,
            latitude=None,
            longitude=None,
        )

    messages.success(request, "Ride marked as completed.")
    return redirect("assigned_driver_rides")


@approved_driver_required
def confirm_assigned_ride_pickup(request, ride_id):
    """Record explicit pickup confirmation for the assigned driver."""
    from django.db import transaction
    from django.http import HttpResponseNotAllowed
    from django.shortcuts import get_object_or_404
    from django.utils import timezone

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, "Your account profile is missing.")
        return redirect("account_dashboard")

    if (
        profile.role != UserProfile.Role.DRIVER
        or profile.driver_status != UserProfile.DriverStatus.APPROVED
    ):
        messages.error(request, "Only approved drivers can confirm pickup.")
        return redirect("account_dashboard")

    with transaction.atomic():
        ride = get_object_or_404(
            TransportRequest.objects.select_for_update(),
            pk=ride_id,
            assigned_driver=request.user,
        )

        if ride.status != TransportRequest.Status.CONFIRMED:
            messages.error(
                request,
                "Pickup can only be confirmed for a confirmed ride.",
            )
            return redirect("driver_ride_navigation", ride_id=ride.pk)

        if ride.pickup_confirmed_at is None:
            ride.pickup_confirmed_at = timezone.now()
            ride.save(update_fields=["pickup_confirmed_at"])

    messages.success(
        request,
        "Pickup confirmed. Navigation can now proceed to the destination.",
    )
    return redirect("driver_ride_navigation", ride_id=ride_id)

@approved_driver_required
def driver_ride_navigation(request, ride_id):
    """Show navigation endpoints for a ride assigned to this approved driver."""
    from django.shortcuts import get_object_or_404

    ride = get_object_or_404(
        TransportRequest,
        pk=ride_id,
        assigned_driver=request.user,
    )

    pickup = None
    destination = None

    if ride.pickup_latitude is not None and ride.pickup_longitude is not None:
        pickup = f"{ride.pickup_latitude},{ride.pickup_longitude}"

    if (
        ride.destination_latitude is not None
        and ride.destination_longitude is not None
    ):
        destination = (
            f"{ride.destination_latitude},{ride.destination_longitude}"
        )

    google_maps_url = None
    if pickup and destination:
        from urllib.parse import urlencode

        google_maps_url = (
            "https://www.google.com/maps/dir/?"
            + urlencode({
                "api": "1",
                "origin": pickup,
                "destination": destination,
                "travelmode": "driving",
            })
        )

    return render(
        request,
        "accounts/driver_ride_navigation.html",
        {
            "ride": ride,
            "pickup_confirmed": ride.pickup_confirmed_at is not None,
            "pickup_coordinates": pickup,
            "destination_coordinates": destination,
            "google_maps_url": google_maps_url,
            "thunderforest_api_key": os.environ.get("THUNDERFOREST_API_KEY", ""),
        },
    )

