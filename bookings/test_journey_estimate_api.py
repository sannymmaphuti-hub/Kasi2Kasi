import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from bookings.models import TransportRequest
from bookings.journey_estimator import JourneyEstimationError


User = get_user_model()


class JourneyEstimateAPITests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="estimatecustomer",
            password="Customer!Secure2026",
        )
        UserProfile.objects.create(
            user=self.customer,
            role=UserProfile.Role.CUSTOMER,
        )
        self.url = reverse("journey_estimate_api")
        self.payload = {
            "pickup_latitude": "-23.750000",
            "pickup_longitude": "29.950000",
            "destination_latitude": "-23.900000",
            "destination_longitude": "29.400000",
        }
        self.estimate = SimpleNamespace(
            distance_km=Decimal("12.5"),
            duration_minutes=Decimal("30.0"),
            provider="OSRM",
        )

    def post_payload(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    @patch("bookings.views.estimate_journey")
    def test_customer_receives_indicative_journey_estimate(self, mock_estimate):
        self.client.force_login(self.customer)
        mock_estimate.return_value = self.estimate

        response = self.post_payload(self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["distance_km"], "12.5")
        self.assertEqual(response.json()["duration_minutes"], "30.0")
        self.assertEqual(response.json()["provider"], "OSRM")
        self.assertTrue(response.json()["indicative"])
        mock_estimate.assert_called_once_with(
            pickup_latitude=Decimal("-23.750000"),
            pickup_longitude=Decimal("29.950000"),
            destination_latitude=Decimal("-23.900000"),
            destination_longitude=Decimal("29.400000"),
        )
        self.assertEqual(TransportRequest.objects.count(), 0)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.post_payload(self.payload)

        self.assertEqual(response.status_code, 302)
        self.assertIn("next=", response.url)

    def test_driver_account_is_forbidden(self):
        driver = User.objects.create_user(
            username="estimatedriver",
            password="Driver!Secure2026",
        )
        UserProfile.objects.create(
            user=driver,
            role=UserProfile.Role.DRIVER,
        )
        self.client.force_login(driver)

        with patch("bookings.views.estimate_journey") as mock_estimate:
            response = self.post_payload(self.payload)

        self.assertEqual(response.status_code, 403)
        mock_estimate.assert_not_called()

    def test_get_method_is_not_allowed(self):
        self.client.force_login(self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

    def test_invalid_json_is_rejected(self):
        self.client.force_login(self.customer)

        response = self.client.post(
            self.url,
            data="{not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_json_array_is_rejected(self):
        self.client.force_login(self.customer)

        response = self.client.post(
            self.url,
            data=json.dumps([1, 2, 3]),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_missing_coordinate_is_rejected(self):
        self.client.force_login(self.customer)
        payload = self.payload.copy()
        payload.pop("pickup_latitude")

        with patch("bookings.views.estimate_journey") as mock_estimate:
            response = self.post_payload(payload)

        self.assertEqual(response.status_code, 400)
        mock_estimate.assert_not_called()

    def test_boolean_coordinate_is_rejected(self):
        self.client.force_login(self.customer)
        payload = self.payload.copy()
        payload["pickup_latitude"] = True

        with patch("bookings.views.estimate_journey") as mock_estimate:
            response = self.post_payload(payload)

        self.assertEqual(response.status_code, 400)
        mock_estimate.assert_not_called()

    def test_out_of_range_coordinate_is_rejected(self):
        self.client.force_login(self.customer)
        payload = self.payload.copy()
        payload["pickup_longitude"] = "181"

        with patch("bookings.views.estimate_journey") as mock_estimate:
            response = self.post_payload(payload)

        self.assertEqual(response.status_code, 400)
        mock_estimate.assert_not_called()

    def test_identical_pickup_and_destination_are_rejected(self):
        self.client.force_login(self.customer)
        payload = self.payload.copy()
        payload["destination_latitude"] = payload["pickup_latitude"]
        payload["destination_longitude"] = payload["pickup_longitude"]

        with patch("bookings.views.estimate_journey") as mock_estimate:
            response = self.post_payload(payload)

        self.assertEqual(response.status_code, 400)
        mock_estimate.assert_not_called()

    @patch("bookings.views.estimate_journey")
    def test_routing_failure_returns_service_unavailable(self, mock_estimate):
        self.client.force_login(self.customer)
        mock_estimate.side_effect = JourneyEstimationError("routing failed")

        response = self.post_payload(self.payload)

        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily unavailable", response.json()["error"])

    @patch("bookings.views.estimate_journey")
    def test_estimate_does_not_change_existing_booking_fares(self, mock_estimate):
        self.client.force_login(self.customer)
        mock_estimate.return_value = self.estimate
        booking = TransportRequest.objects.create(
            customer=self.customer,
            customer_name="Test Passenger",
            contact_number="0712345678",
            pickup_location="Bochum",
            destination="Witten",
            proposed_fare=Decimal("75.00"),
            agreed_fare=None,
            status=TransportRequest.Status.PENDING,
            travel_datetime="2026-11-01T12:00:00+02:00",
            passenger_count=1,
        )

        response = self.post_payload(self.payload)

        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.proposed_fare, Decimal("75.00"))
        self.assertIsNone(booking.agreed_fare)
        self.assertEqual(booking.status, TransportRequest.Status.PENDING)
