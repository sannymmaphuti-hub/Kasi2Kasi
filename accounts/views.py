from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import RegistrationForm
from .permissions import approved_driver_required
from bookings.models import TransportRequest
from .models import UserProfile


def register(request, role):
    if role not in (
        UserProfile.Role.CUSTOMER,
        UserProfile.Role.DRIVER,
    ):
        return redirect("home")

    if request.user.is_authenticated:
        return redirect("account_dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)

            # Save the user and role profile together.
            from django.db import transaction

            with transaction.atomic():
                user.save()

                profile = UserProfile(
                    user=user,
                    role=role,
                )
                profile.save()

            login(request, user)

            if role == UserProfile.Role.DRIVER:
                messages.success(
                    request,
                    "Your driver account has been created. "
                    "Your account requires approval before you can "
                    "access driver opportunities.",
                )
            else:
                messages.success(
                    request,
                    "Your customer account has been created.",
                )

            return redirect("account_dashboard")
    else:
        form = RegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
            "role": role,
            "is_driver_registration": (
                role == UserProfile.Role.DRIVER
            ),
        },
    )


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse("account_dashboard")


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
        return render(
            request,
            "accounts/driver_dashboard.html",
            {"profile": profile},
        )

    return render(
        request,
        "accounts/customer_dashboard.html",
        {"profile": profile},
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
            "ride_sections": [
                ("Upcoming rides", upcoming_rides),
                ("Past rides", past_rides),
                ("Completed rides", completed_rides),
                ("Cancelled rides", cancelled_rides),
            ],
        },
    )

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



