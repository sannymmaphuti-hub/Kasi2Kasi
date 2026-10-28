from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserProfile
from .models import TransportRequest


User = get_user_model()


@staff_member_required
def dispatch_overview(request):
    """Staff-only operational overview of rides and available drivers."""

    rides = TransportRequest.objects.select_related(
        "customer",
        "assigned_driver",
    ).order_by("travel_datetime", "-created_at")

    selected_status = request.GET.get("status", "").strip()
    selected_driver = request.GET.get("driver", "").strip()

    valid_statuses = {
        value for value, label in TransportRequest.Status.choices
    }

    if selected_status in valid_statuses:
        rides = rides.filter(status=selected_status)
    else:
        selected_status = ""

    if selected_driver.isdigit():
        rides = rides.filter(assigned_driver_id=int(selected_driver))
    else:
        selected_driver = ""

    ride_counts = TransportRequest.objects.aggregate(
        total=Count("id"),
        pending=Count(
            "id",
            filter=Q(status=TransportRequest.Status.PENDING),
        ),
        accepted=Count(
            "id",
            filter=Q(status=TransportRequest.Status.ACCEPTED),
        ),
        confirmed=Count(
            "id",
            filter=Q(status=TransportRequest.Status.CONFIRMED),
        ),
        completed=Count(
            "id",
            filter=Q(status=TransportRequest.Status.COMPLETED),
        ),
        cancelled=Count(
            "id",
            filter=Q(status=TransportRequest.Status.CANCELLED),
        ),
        unassigned=Count(
            "id",
            filter=Q(assigned_driver__isnull=True)
            & ~Q(status=TransportRequest.Status.CANCELLED)
            & ~Q(status=TransportRequest.Status.COMPLETED),
        ),
    )

    active_statuses = (
        TransportRequest.Status.PENDING,
        TransportRequest.Status.ACCEPTED,
        TransportRequest.Status.CONFIRMED,
    )

    ride_counts["assigned_active"] = TransportRequest.objects.filter(
        assigned_driver__isnull=False,
        status__in=active_statuses,
    ).count()

    available_drivers = User.objects.filter(
        profile__role=UserProfile.Role.DRIVER,
        profile__driver_status=UserProfile.DriverStatus.APPROVED,
        profile__is_available=True,
    ).select_related("profile").order_by("username")

    context = {
        "rides": rides,
        "ride_counts": ride_counts,
        "available_drivers": available_drivers,
        "statuses": TransportRequest.Status.choices,
        "selected_status": selected_status,
        "selected_driver": selected_driver,
    }

    return render(request, "bookings/dispatch_overview.html", context)


@staff_member_required
def assign_dispatch_ride(request, ride_id):
    """Assign an unassigned pending ride to an approved online driver."""

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    driver_id = request.POST.get("driver_id", "").strip()

    if not driver_id.isdigit():
        messages.error(request, "Select a valid available driver.")
        return redirect("dispatch_overview")

    active_statuses = (
        TransportRequest.Status.PENDING,
        TransportRequest.Status.ACCEPTED,
        TransportRequest.Status.CONFIRMED,
    )

    with transaction.atomic():
        ride = get_object_or_404(
            TransportRequest.objects.select_for_update(),
            pk=ride_id,
        )

        if ride.status != TransportRequest.Status.PENDING:
            messages.error(
                request,
                "Only pending rides can be assigned from dispatch.",
            )
            return redirect("dispatch_overview")

        if ride.assigned_driver_id is not None:
            messages.error(
                request,
                "This ride already has an assigned driver.",
            )
            return redirect("dispatch_overview")

        driver = User.objects.filter(
            pk=int(driver_id),
            profile__role=UserProfile.Role.DRIVER,
            profile__driver_status=UserProfile.DriverStatus.APPROVED,
            profile__is_available=True,
        ).first()

        if driver is None:
            messages.error(
                request,
                "The selected driver is not an approved, available driver.",
            )
            return redirect("dispatch_overview")

        conflict = TransportRequest.objects.filter(
            assigned_driver=driver,
            travel_datetime=ride.travel_datetime,
            status__in=active_statuses,
        ).exists()

        if conflict:
            messages.error(
                request,
                (
                    "Assignment rejected: this driver already has an "
                    "active ride at the same departure time."
                ),
            )
            return redirect("dispatch_overview")

        ride.assigned_driver = driver
        ride.save(update_fields=["assigned_driver"])

    messages.success(
        request,
        f"Ride #{ride_id} assigned to {driver.get_full_name() or driver.username}.",
    )
    return redirect("dispatch_overview")
