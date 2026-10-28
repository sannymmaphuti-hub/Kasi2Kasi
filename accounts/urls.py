from .gps_views import driver_location_api
from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    AccountLoginView,
    account_dashboard,
    driver_vehicle_management,
    toggle_vehicle_active,
    toggle_driver_availability,
    assigned_driver_rides,
    driver_ride_navigation,
    propose_assigned_ride_fare,
    accept_assigned_ride,
    complete_assigned_ride,
    confirm_assigned_ride_pickup,
    profile_settings,
    register,
)

urlpatterns = [
    path("driver/rides/<int:ride_id>/location/", driver_location_api, name="driver_location_api"),
    path("driver/rides/<int:ride_id>/confirm-pickup/", confirm_assigned_ride_pickup, name="confirm_assigned_ride_pickup"),

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
        "driver/vehicles/",
        driver_vehicle_management,
        name="driver_vehicle_management",
    ),
    path(
        "driver/vehicles/<int:vehicle_id>/edit/",
        driver_vehicle_management,
        name="driver_vehicle_edit",
    ),
    path(
        "driver/vehicles/<int:vehicle_id>/toggle-active/",
        toggle_vehicle_active,
        name="toggle_vehicle_active",
    ),
    path(
        "driver/availability/",
        toggle_driver_availability,
        name="toggle_driver_availability",
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
    path(
        "driver/rides/<int:ride_id>/navigate/",
        driver_ride_navigation,
        name="driver_ride_navigation",
    ),
    path(
        "driver/rides/<int:ride_id>/propose-fare/",
        propose_assigned_ride_fare,
        name="propose_assigned_ride_fare",
    ),
    path(
        "driver/rides/<int:ride_id>/accept/",
        accept_assigned_ride,
        name="accept_assigned_ride",
    ),
    path(
        "driver/rides/<int:ride_id>/complete/",
        complete_assigned_ride,
        name="complete_assigned_ride",
    ),
]
