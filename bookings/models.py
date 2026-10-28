from django.conf import settings
from django.db import models


class TransportRequest(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="transport_requests",
        null=True,
        blank=True,
    )

    assigned_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_transport_requests",
        null=True,
        blank=True,
        limit_choices_to={
            "profile__role": "DRIVER",
            "profile__driver_status": "APPROVED",
        },
    )

    # Original server-calculated estimate, if pricing was available.
    estimated_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    proposed_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    agreed_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        CONFIRMED = "CONFIRMED", "Confirmed"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    customer_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=20)

    pickup_location = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)

    # Optional map coordinates. Existing and manually entered
    # bookings remain valid without coordinates.
    pickup_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    pickup_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    destination_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    destination_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    travel_datetime = models.DateTimeField()
    passenger_count = models.PositiveSmallIntegerField(default=1)
    additional_notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    pickup_confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the assigned driver explicitly confirmed passenger pickup.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return (
            f"{self.customer_name}: "
            f"{self.pickup_location} -> {self.destination}"
        )



class DriverLiveLocation(models.Model):
    """Latest driver location for one assigned ride; no location history."""

    ride = models.OneToOneField(
        TransportRequest,
        on_delete=models.CASCADE,
        related_name="driver_live_location",
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="live_ride_locations",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    is_sharing = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Live location for ride {self.ride_id}"
