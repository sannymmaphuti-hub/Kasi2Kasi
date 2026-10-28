from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        DRIVER = "DRIVER", "Driver"

    class DriverStatus(models.TextChoices):
        NOT_APPLICABLE = "NOT_APPLICABLE", "Not applicable"
        PENDING = "PENDING", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SUSPENDED = "SUSPENDED", "Suspended"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )

    driver_status = models.CharField(
        max_length=15,
        choices=DriverStatus.choices,
        default=DriverStatus.NOT_APPLICABLE,
    )

    is_available = models.BooleanField(
        default=False,
        help_text="Whether this approved driver is currently available for new assignments.",
    )

    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.role == self.Role.CUSTOMER:
            self.driver_status = self.DriverStatus.NOT_APPLICABLE
        elif self.driver_status == self.DriverStatus.NOT_APPLICABLE:
            self.driver_status = self.DriverStatus.PENDING

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} ΓÇö {self.get_role_display()}"

class DriverVehicle(models.Model):
    """Vehicle registered by a driver for administrative verification."""

    class VehicleType(models.TextChoices):
        SEDAN = "SEDAN", "Sedan"
        HATCHBACK = "HATCHBACK", "Hatchback"
        SUV = "SUV", "SUV"
        MINIBUS = "MINIBUS", "Minibus"
        BAKKIE = "BAKKIE", "Bakkie"
        MOTORCYCLE = "MOTORCYCLE", "Motorcycle"
        TRUCK = "TRUCK", "Truck"
        OTHER = "OTHER", "Other"

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="registered_vehicles",
        limit_choices_to={"profile__role": "DRIVER"},
    )
    vehicle_type = models.CharField(max_length=15, choices=VehicleType.choices)
    make = models.CharField(max_length=60)
    model = models.CharField(max_length=60)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    registration_number = models.CharField(max_length=20)
    passenger_capacity = models.PositiveSmallIntegerField(default=4)
    is_active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["registration_number"],
                name="unique_driver_vehicle_registration",
            ),
        ]

    def __str__(self):
        return f"{self.make} {self.model} ({self.registration_number})"
