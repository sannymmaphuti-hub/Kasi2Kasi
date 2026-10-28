from django.urls import path

from . import views
from .customer_tracking import customer_ride_location_api, customer_ride_tracking_page
from .dispatch import assign_dispatch_ride, dispatch_overview

urlpatterns = [
    path("", views.home, name="home"),
    path("journey-estimate/", views.journey_estimate_api, name="journey_estimate_api"),
    path("reverse-geocode/", views.reverse_geocode_api, name="reverse_geocode_api"),
    path("request-ride/", views.request_ride, name="request_ride"),
    path("my-rides/", views.my_rides, name="my_rides"),
    path(
        "my-rides/<int:ride_id>/track/",
        customer_ride_tracking_page,
        name="customer_ride_tracking_page",
    ),
    path(
        "my-rides/<int:ride_id>/live-location/",
        customer_ride_location_api,
        name="customer_ride_location_api",
    ),
    path(
        "my-rides/<int:ride_id>/confirm-fare/",
        views.confirm_ride_fare,
        name="confirm_ride_fare",
    ),
    path(
        "my-rides/<int:ride_id>/cancel/",
        views.cancel_ride,
        name="cancel_ride",
    ),
    path(
        "dispatch/",
        dispatch_overview,
        name="dispatch_overview",
    ),
    path(
        "dispatch/rides/<int:ride_id>/assign/",
        assign_dispatch_ride,
        name="assign_dispatch_ride",
    ),
]
