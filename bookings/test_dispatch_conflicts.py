from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import UserProfile
from bookings.admin import TransportRequestAdminForm
from bookings.models import TransportRequest


User = get_user_model()


class DispatchAssignmentConflictTests(TestCase):
    def setUp(self):
        self.driver = User.objects.create_user(
            username="dispatch_conflict_driver",
            password="TestPassword!2026",
        )
        UserProfile.objects.create(
            user=self.driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
            is_available=True,
        )

        self.departure = timezone.localtime(
            timezone.now() + timedelta(days=3)
        ).replace(second=0, microsecond=0)

    def create_ride(self, status):
        return TransportRequest.objects.create(
            assigned_driver=self.driver,
            customer_name="Existing Passenger",
            contact_number="0712345678",
            pickup_location="Soweto",
            destination="Johannesburg",
            travel_datetime=self.departure,
            passenger_count=1,
            proposed_fare=Decimal("100.00"),
            agreed_fare=(
                Decimal("100.00")
                if status in (
                    TransportRequest.Status.CONFIRMED,
                    TransportRequest.Status.COMPLETED,
                )
                else None
            ),
            status=status,
        )

    def form_data(self):
        return {
            "customer": "",
            "assigned_driver": str(self.driver.pk),
            "customer_name": "New Passenger",
            "contact_number": "0723456789",
            "pickup_location": "Soweto",
            "pickup_latitude": "",
            "pickup_longitude": "",
            "destination": "Pretoria",
            "destination_latitude": "",
            "destination_longitude": "",
            "travel_datetime": self.departure.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "passenger_count": "1",
            "additional_notes": "",
            "proposed_fare": "",
            "agreed_fare": "",
            "status": TransportRequest.Status.PENDING,
        }

    def test_same_departure_time_active_assignment_is_rejected(self):
        self.create_ride(TransportRequest.Status.CONFIRMED)

        form = TransportRequestAdminForm(data=self.form_data())

        self.assertFalse(form.is_valid())
        self.assertIn("assigned_driver", form.errors)
        self.assertIn(
            "same departure time",
            str(form.errors["assigned_driver"]),
        )

    def test_completed_ride_does_not_block_assignment(self):
        self.create_ride(TransportRequest.Status.COMPLETED)

        form = TransportRequestAdminForm(data=self.form_data())

        self.assertTrue(form.is_valid(), form.errors)

    def test_cancelled_ride_does_not_block_assignment(self):
        self.create_ride(TransportRequest.Status.CANCELLED)

        form = TransportRequestAdminForm(data=self.form_data())

        self.assertTrue(form.is_valid(), form.errors)

    def test_different_departure_time_does_not_conflict(self):
        existing = self.create_ride(TransportRequest.Status.CONFIRMED)
        existing.travel_datetime += timedelta(minutes=1)
        existing.save(update_fields=["travel_datetime"])

        form = TransportRequestAdminForm(data=self.form_data())

        self.assertTrue(form.is_valid(), form.errors)
