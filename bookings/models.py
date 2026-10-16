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

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.customer_name}: "
            f"{self.pickup_location} -> {self.destination}"
        )

