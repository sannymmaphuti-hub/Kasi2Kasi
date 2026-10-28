from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from bookings.models import DriverLiveLocation, TransportRequest


User = get_user_model()


class CustomerRideTrackingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(
            username="tracking_customer",
            password="TestPassword123!",
        )
        cls.other_customer = User.objects.create_user(
            username="other_tracking_customer",
            password="TestPassword123!",
        )
        cls.driver = User.objects.create_user(
            username="tracking_driver",
            password="TestPassword123!",
        )

        UserProfile.objects.create(
            user=cls.customer,
            role=UserProfile.Role.CUSTOMER,
        )
        UserProfile.objects.create(
            user=cls.other_customer,
            role=UserProfile.Role.CUSTOMER,
        )
        UserProfile.objects.create(
            user=cls.driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
        )

        cls.ride = TransportRequest.objects.create(
            customer=cls.customer,
            customer_name="Tracking Customer",
            status=TransportRequest.Status.CONFIRMED,
            assigned_driver=cls.driver,
            travel_datetime=timezone.now() + timedelta(days=1),
        )

    def setUp(self):
        self.url = reverse(
            "customer_ride_location_api",
            kwargs={"ride_id": self.ride.pk},
        )
        self.client.force_login(self.customer)

    def create_location(self, **overrides):
        defaults = {
            "ride": self.ride,
            "driver": self.driver,
            "latitude": Decimal("-25.749041"),
            "longitude": Decimal("28.217831"),
            "is_sharing": True,
        }
        defaults.update(overrides)
        return DriverLiveLocation.objects.create(**defaults)

    def test_customer_receives_fresh_shared_driver_location(self):
        location = self.create_location()
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["sharing"])
        self.assertTrue(response.json()["available"])
        self.assertEqual(response.json()["latitude"], str(location.latitude))
        self.assertEqual(response.json()["longitude"], str(location.longitude))

    def test_other_customer_cannot_access_ride_location(self):
        self.client.force_login(self.other_customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_driver_account_cannot_use_customer_tracking_endpoint(self):
        self.client.force_login(self.driver)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_location_is_not_returned_when_sharing_is_off(self):
        self.create_location(is_sharing=False)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["sharing"])
        self.assertNotIn("latitude", response.json())

    def test_stale_location_is_not_returned(self):
        location = self.create_location()
        location.updated_at = timezone.now() - timedelta(minutes=3)
        DriverLiveLocation.objects.filter(pk=location.pk).update(
            updated_at=location.updated_at
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["available"])
        self.assertNotIn("latitude", response.json())

    def test_location_without_coordinates_is_not_returned(self):
        self.create_location(latitude=None, longitude=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["available"])
        self.assertNotIn("latitude", response.json())

    def test_pending_ride_does_not_expose_location(self):
        self.ride.status = TransportRequest.Status.PENDING
        self.ride.save(update_fields=["status"])
        self.create_location()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["available"])
        self.assertNotIn("latitude", response.json())

    def test_endpoint_is_read_only(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 405)

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
