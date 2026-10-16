from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.models import UserProfile
from .forms import TransportRequestForm
from .models import TransportRequest


def home(request):
    return render(request, "home.html")


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
