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
        return f"{self.user.username} — {self.get_role_display()}"
