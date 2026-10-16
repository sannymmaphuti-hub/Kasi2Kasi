from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("request-ride/", views.request_ride, name="request_ride"),
    path("my-rides/", views.my_rides, name="my_rides"),
]
