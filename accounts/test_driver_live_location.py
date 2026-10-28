import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from bookings.models import DriverLiveLocation, TransportRequest


User = get_user_model()


class DriverLiveLocationAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.driver = User.objects.create_user(
            username="gps_approved_driver",
            password="Test-password-123!",
        )
        cls.driver_profile = UserProfile.objects.create(
            user=cls.driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
            is_available=True,
        )

        cls.other_driver = User.objects.create_user(
            username="gps_other_driver",
            password="Test-password-123!",
        )
        UserProfile.objects.create(
            user=cls.other_driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
            is_available=True,
        )

        cls.pending_driver = User.objects.create_user(
            username="gps_pending_driver",
            password="Test-password-123!",
        )
        UserProfile.objects.create(
            user=cls.pending_driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.PENDING,
            is_available=False,
        )

        cls.customer = User.objects.create_user(
            username="gps_customer",
            password="Test-password-123!",
        )
        UserProfile.objects.create(
            user=cls.customer,
            role=UserProfile.Role.CUSTOMER,
        )

        cls.ride = TransportRequest.objects.create(
            customer=cls.customer,
            assigned_driver=cls.driver,
            pickup_location="GPS test pickup",
            destination="GPS test destination",
            travel_datetime=timezone.now() + timedelta(hours=2),
            status=TransportRequest.Status.ACCEPTED,
        )

    def setUp(self):
        self.url = reverse(
            "driver_location_api",
            kwargs={"ride_id": self.ride.pk},
        )
        self.client.force_login(self.driver)

    def post_action(self, action, **extra):
        payload = {"action": action, **extra}
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_start_sharing_creates_location_without_changing_ride(self):
        original_status = self.ride.status
        original_driver_id = self.ride.assigned_driver_id

        response = self.post_action("start")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["sharing"])

        location = DriverLiveLocation.objects.get(ride=self.ride)
        self.assertEqual(location.driver_id, self.driver.pk)
        self.assertTrue(location.is_sharing)
        self.assertIsNone(location.latitude)
        self.assertIsNone(location.longitude)

        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, original_status)
        self.assertEqual(self.ride.assigned_driver_id, original_driver_id)

    def test_restarting_sharing_clears_previous_coordinates_until_new_fix(self):
        self.assertEqual(self.post_action("start").status_code, 200)

        self.assertEqual(
            self.post_action(
                "update",
                latitude=-26.2041,
                longitude=28.0473,
            ).status_code,
            200,
        )

        self.assertEqual(self.post_action("stop").status_code, 200)

        response = self.post_action("start")
        self.assertEqual(response.status_code, 200)

        location = DriverLiveLocation.objects.get(ride=self.ride)
        self.assertTrue(location.is_sharing)
        self.assertIsNone(location.latitude)
        self.assertIsNone(location.longitude)

        tracking_url = reverse(
            "customer_ride_location_api",
            kwargs={"ride_id": self.ride.pk},
        )

        self.client.force_login(self.customer)
        tracking_response = self.client.get(tracking_url)

        self.assertEqual(tracking_response.status_code, 200)
        self.assertTrue(tracking_response.json()["sharing"])
        self.assertFalse(tracking_response.json()["available"])
        self.assertNotIn("latitude", tracking_response.json())
        self.assertNotIn("longitude", tracking_response.json())
    def test_update_before_start_is_rejected(self):
        response = self.post_action(
            "update",
            latitude=-26.2041,
            longitude=28.0473,
        )

        self.assertEqual(response.status_code, 409)
        location = DriverLiveLocation.objects.get(ride=self.ride)
        self.assertFalse(location.is_sharing)
        self.assertIsNone(location.latitude)
        self.assertIsNone(location.longitude)

    def test_valid_location_update_after_start(self):
        self.assertEqual(self.post_action("start").status_code, 200)

        response = self.post_action(
            "update",
            latitude=-26.2041,
            longitude=28.0473,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.json()["latitude"]), Decimal("-26.204100"))
        self.assertEqual(Decimal(response.json()["longitude"]), Decimal("28.047300"))

        location = DriverLiveLocation.objects.get(ride=self.ride)
        self.assertTrue(location.is_sharing)
        self.assertEqual(location.latitude, Decimal("-26.204100"))
        self.assertEqual(location.longitude, Decimal("28.047300"))

    def test_invalid_coordinates_are_rejected(self):
        self.post_action("start")

        invalid_payloads = [
            {"latitude": 91, "longitude": 28},
            {"latitude": -26, "longitude": 181},
            {"latitude": "not-a-number", "longitude": 28},
            {"latitude": None, "longitude": 28},
            {"latitude": True, "longitude": 28},
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.post_action("update", **payload)
                self.assertEqual(response.status_code, 400)

        location = DriverLiveLocation.objects.get(ride=self.ride)
        self.assertIsNone(location.latitude)
        self.assertIsNone(location.longitude)

    def test_stop_sharing_disables_location_updates(self):
        self.post_action("start")
        self.post_action(
            "update",
            latitude=-26.2041,
            longitude=28.0473,
        )

        response = self.post_action("stop")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["sharing"])

        location = DriverLiveLocation.objects.get(ride=self.ride)
        self.assertFalse(location.is_sharing)

        update_response = self.post_action(
            "update",
            latitude=-25.0,
            longitude=28.0,
        )
        self.assertEqual(update_response.status_code, 409)

    def test_unassigned_driver_cannot_access_ride_location(self):
        self.client.force_login(self.other_driver)

        response = self.client.post(
            self.url,
            data=json.dumps({"action": "start"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            DriverLiveLocation.objects.filter(ride=self.ride).exists()
        )

    def test_pending_driver_cannot_share_location(self):
        self.client.force_login(self.pending_driver)

        response = self.client.post(
            self.url,
            data=json.dumps({"action": "start"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            DriverLiveLocation.objects.filter(ride=self.ride).exists()
        )

    def test_customer_cannot_share_driver_location(self):
        self.client.force_login(self.customer)

        response = self.client.post(
            self.url,
            data=json.dumps({"action": "start"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_inactive_ride_rejects_start_and_update(self):
        self.ride.status = TransportRequest.Status.COMPLETED
        self.ride.save(update_fields=["status"])

        response = self.post_action("start")

        self.assertEqual(response.status_code, 409)
        self.assertFalse(
            DriverLiveLocation.objects.filter(ride=self.ride).exists()
        )

    def test_malformed_json_is_rejected(self):
        response = self.client.post(
            self.url,
            data="{invalid-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_action_is_rejected(self):
        response = self.post_action("teleport")

        self.assertEqual(response.status_code, 400)

