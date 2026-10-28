from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import UserProfile
from bookings.admin import TransportRequestAdminForm
from bookings.models import TransportRequest


User = get_user_model()


class TransportRequestAdminFormTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="adminformcustomer",
            password="Customer!Secure2026",
        )
        UserProfile.objects.create(
            user=self.customer,
            role=UserProfile.Role.CUSTOMER,
        )

        self.approved_driver = User.objects.create_user(
            username="approvedadminformdriver",
            password="Driver!Secure2026",
        )
        UserProfile.objects.create(
            user=self.approved_driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
            is_available=True,
        )

        self.pending_driver = User.objects.create_user(
            username="pendingadminformdriver",
            password="Driver!Secure2026",
        )
        UserProfile.objects.create(
            user=self.pending_driver,
            role=UserProfile.Role.DRIVER,
        )

    def valid_data(self):
        travel_time = (
            timezone.localtime() + timedelta(days=2)
        ).replace(second=0, microsecond=0)

        return {
            "customer": str(self.customer.pk),
            "assigned_driver": str(self.approved_driver.pk),
            "customer_name": "Test Passenger",
            "contact_number": "0712345678",
            "pickup_location": "Bochum",
            "destination": "Witten",
            "pickup_latitude": "",
            "pickup_longitude": "",
            "destination_latitude": "",
            "destination_longitude": "",
            "travel_datetime": travel_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "passenger_count": "1",
            "additional_notes": "",
            "proposed_fare": "150.00",
            "agreed_fare": "",
            "status": TransportRequest.Status.PENDING,
        }

    def make_form(self, data):
        return TransportRequestAdminForm(
            data=data,
            instance=TransportRequest(),
        )

    def test_approved_driver_can_be_assigned(self):
        form = self.make_form(self.valid_data())

        self.assertTrue(form.is_valid(), form.errors)

        self.assertEqual(
            form.cleaned_data["assigned_driver"],
            self.approved_driver,
        )

    def test_unapproved_driver_cannot_be_assigned(self):
        data = self.valid_data()
        data["assigned_driver"] = str(self.pending_driver.pk)

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("assigned_driver", form.errors)

    def test_zero_proposed_fare_is_rejected(self):
        data = self.valid_data()
        data["proposed_fare"] = "0.00"

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("proposed_fare", form.errors)

    def test_negative_agreed_fare_is_rejected(self):
        data = self.valid_data()
        data["agreed_fare"] = "-10.00"

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("agreed_fare", form.errors)

    def test_agreed_fare_requires_proposed_fare(self):
        data = self.valid_data()
        data["proposed_fare"] = ""
        data["agreed_fare"] = "150.00"

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("agreed_fare", form.errors)

    def test_accepted_ride_requires_assigned_driver(self):
        data = self.valid_data()
        data["assigned_driver"] = ""
        data["status"] = TransportRequest.Status.ACCEPTED

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("assigned_driver", form.errors)

    def test_accepted_ride_requires_proposed_fare(self):
        data = self.valid_data()
        data["proposed_fare"] = ""
        data["status"] = TransportRequest.Status.ACCEPTED

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("proposed_fare", form.errors)

    def test_confirmed_ride_requires_agreed_fare(self):
        data = self.valid_data()
        data["agreed_fare"] = ""
        data["status"] = TransportRequest.Status.CONFIRMED

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("agreed_fare", form.errors)

    def test_completed_ride_requires_agreed_fare(self):
        data = self.valid_data()
        data["agreed_fare"] = ""
        data["status"] = TransportRequest.Status.COMPLETED

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("agreed_fare", form.errors)

    def test_pending_ride_cannot_have_agreed_fare(self):
        data = self.valid_data()
        data["agreed_fare"] = "150.00"
        data["status"] = TransportRequest.Status.PENDING

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("agreed_fare", form.errors)

    def test_accepted_ride_cannot_already_have_agreed_fare(self):
        data = self.valid_data()
        data["agreed_fare"] = "150.00"
        data["status"] = TransportRequest.Status.ACCEPTED

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("agreed_fare", form.errors)
