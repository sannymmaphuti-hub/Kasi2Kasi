from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    AccountLoginView,
    account_dashboard,
    assigned_driver_rides,
    profile_settings,
    register,
)

urlpatterns = [
    path(
        "signup/customer/",
        register,
        {"role": "CUSTOMER"},
        name="customer_signup",
    ),
    path(
        "signup/driver/",
        register,
        {"role": "DRIVER"},
        name="driver_signup",
    ),
    path(
        "login/",
        AccountLoginView.as_view(),
        name="account_login",
    ),
    path(
        "logout/",
        LogoutView.as_view(),
        name="account_logout",
    ),
    path(
        "dashboard/",
        account_dashboard,
        name="account_dashboard",
    ),
    path(
        "profile/",
        profile_settings,
        name="profile_settings",
    ),
    path(
        "driver/rides/",
        assigned_driver_rides,
        name="assigned_driver_rides",
    ),
]