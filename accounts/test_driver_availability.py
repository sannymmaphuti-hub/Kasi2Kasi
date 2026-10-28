from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from bookings.admin import TransportRequestAdminForm
from bookings.models import TransportRequest


User = get_user_model()


class DriverAvailabilityViewTests(TestCase):
    def setUp(self):
        self.driver = User.objects.create_user(
            username="availability_driver",
            password="Driver!Secure2026",
        )
        self.profile = UserProfile.objects.create(
            user=self.driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
        )
        self.url = reverse("toggle_driver_availability")

    def test_approved_driver_can_go_online(self):
        self.client.force_login(self.driver)

        response = self.client.post(self.url, {"available": "on"})

        self.assertRedirects(response, reverse("account_dashboard"))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_available)

    def test_approved_driver_can_go_offline(self):
        self.profile.is_available = True
        self.profile.save(update_fields=["is_available"])
        self.client.force_login(self.driver)

        response = self.client.post(self.url, {"available": "off"})

        self.assertRedirects(response, reverse("account_dashboard"))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_available)

    def test_get_request_is_not_allowed(self):
        self.client.force_login(self.driver)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

    def test_pending_driver_cannot_change_availability(self):
        self.profile.driver_status = UserProfile.DriverStatus.PENDING
        self.profile.save(update_fields=["driver_status"])
        self.client.force_login(self.driver)

        response = self.client.post(self.url, {"available": "on"})

        self.assertRedirects(response, reverse("account_dashboard"))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_available)

    def test_customer_cannot_change_availability(self):
        customer = User.objects.create_user(
            username="availability_customer",
            password="Customer!Secure2026",
        )
        customer_profile = UserProfile.objects.create(
            user=customer,
            role=UserProfile.Role.CUSTOMER,
        )
        self.client.force_login(customer)

        response = self.client.post(self.url, {"available": "on"})

        self.assertRedirects(response, reverse("account_dashboard"))
        customer_profile.refresh_from_db()
        self.assertFalse(customer_profile.is_available)

    def test_invalid_availability_value_is_rejected(self):
        self.client.force_login(self.driver)

        response = self.client.post(self.url, {"available": "maybe"})

        self.assertRedirects(response, reverse("account_dashboard"))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_available)

    def test_going_offline_does_not_remove_existing_assignment(self):
        self.profile.is_available = True
        self.profile.save(update_fields=["is_available"])

        ride = TransportRequest.objects.create(
            assigned_driver=self.driver,
            customer_name="Existing Passenger",
            contact_number="0712345678",
            pickup_location="Soweto",
            destination="Johannesburg",
            travel_datetime=(
                timezone.localtime(timezone.now() + timedelta(days=3))
            ).replace(second=0, microsecond=0),
            passenger_count=1,
            proposed_fare=Decimal("100.00"),
            status=TransportRequest.Status.PENDING,
        )

        self.client.force_login(self.driver)
        response = self.client.post(self.url, {"available": "off"})

        self.assertRedirects(response, reverse("account_dashboard"))
        self.profile.refresh_from_db()
        ride.refresh_from_db()

        self.assertFalse(self.profile.is_available)
        self.assertEqual(ride.assigned_driver_id, self.driver.pk)


class OfflineDriverAssignmentTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="availability_admin_customer",
            password="Customer!Secure2026",
        )
        UserProfile.objects.create(
            user=self.customer,
            role=UserProfile.Role.CUSTOMER,
        )

        self.online_driver = User.objects.create_user(
            username="online_assignment_driver",
            password="Driver!Secure2026",
        )
        UserProfile.objects.create(
            user=self.online_driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
            is_available=True,
        )

        self.offline_driver = User.objects.create_user(
            username="offline_assignment_driver",
            password="Driver!Secure2026",
        )
        UserProfile.objects.create(
            user=self.offline_driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
            is_available=False,
        )

    def form_data(self, driver):
        travel_time = (
            timezone.localtime(timezone.now() + timedelta(days=4))
        ).replace(second=0, microsecond=0)

        return {
            "customer": str(self.customer.pk),
            "assigned_driver": str(driver.pk),
            "customer_name": "Test Passenger",
            "contact_number": "0712345678",
            "pickup_location": "Soweto",
            "destination": "Johannesburg",
            "pickup_latitude": "",
            "pickup_longitude": "",
            "destination_latitude": "",
            "destination_longitude": "",
            "travel_datetime": travel_time.strftime("%Y-%m-%d %H:%M:%S"),
            "passenger_count": "1",
            "additional_notes": "",
            "proposed_fare": "150.00",
            "agreed_fare": "",
            "status": TransportRequest.Status.PENDING,
        }

    def test_online_approved_driver_can_be_assigned(self):
        form = TransportRequestAdminForm(
            data=self.form_data(self.online_driver),
            instance=TransportRequest(),
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_offline_driver_cannot_receive_new_assignment(self):
        form = TransportRequestAdminForm(
            data=self.form_data(self.offline_driver),
            instance=TransportRequest(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("assigned_driver", form.errors)
