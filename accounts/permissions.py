from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import UserProfile


def approved_driver_required(view_func):
    """
    Permit access only to authenticated, approved driver accounts.
    """
    @login_required
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            messages.error(
                request,
                "Your account profile is missing. Please contact support.",
            )
            return redirect("account_dashboard")

        if profile.role != UserProfile.Role.DRIVER:
            messages.error(
                request,
                "This area is available to approved drivers only.",
            )
            return redirect("account_dashboard")

        if profile.driver_status != UserProfile.DriverStatus.APPROVED:
            messages.warning(
                request,
                "Your driver account is not approved for driver opportunities.",
            )
            return redirect("account_dashboard")

        return view_func(request, *args, **kwargs)

    return wrapped_view
