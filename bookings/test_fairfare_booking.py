from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile
from bookings.journey_estimator import JourneyEstimationError
from bookings.models import TransportRequest


User = get_user_model()


class FairFareBookingTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="fairfarecustomer",
            password="Customer!Secure2026",
            first_name="Test",
            last_name="Passenger",
        )
        UserProfile.objects.create(
            user=self.customer,
            role=UserProfile.Role.CUSTOMER,
        )
        self.client.force_login(self.customer)
        self.url = reverse("request_ride")

        future_datetime = (
            __import__("django.utils.timezone", fromlist=["timezone"])
            .localtime()
        )
        from datetime import timedelta
        future_datetime = (
            future_datetime + timedelta(days=2)
        ).replace(second=0, microsecond=0)

        self.data = {
            "customer_name": "Test Passenger",
            "contact_number": "0712345678",
            "pickup_location": "Bochum",
            "pickup_latitude": "-23.750000",
            "pickup_longitude": "29.950000",
            "destination": "Witten",
            "destination_latitude": "-23.900000",
            "destination_longitude": "29.400000",
            "travel_datetime": future_datetime.strftime("%Y-%m-%dT%H:%M"),
            "passenger_count": 1,
            "additional_notes": "",
        }

        self.estimate = SimpleNamespace(
            distance_km=Decimal("12.50"),
            duration_minutes=Decimal("30.00"),
        )

    @override_settings(
        KASI2KASI_BASE_FARE="20.00",
        KASI2KASI_RATE_PER_KM="2.00",
        KASI2KASI_RATE_PER_MINUTE="1.00",
    )
    @patch("bookings.views.estimate_journey")
    def test_request_saves_server_calculated_original_estimate(
        self, mock_estimate
    ):
        mock_estimate.return_value = self.estimate

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 302)
        booking = TransportRequest.objects.get()

        # 20.00 base + (12.50 * 2.00) + (30.00 * 1.00)
        self.assertEqual(booking.estimated_fare, Decimal("75.00"))
        self.assertIsNone(booking.proposed_fare)
        self.assertIsNone(booking.agreed_fare)

        mock_estimate.assert_called_once_with(
            pickup_latitude=Decimal("-23.750000"),
            pickup_longitude=Decimal("29.950000"),
            destination_latitude=Decimal("-23.900000"),
            destination_longitude=Decimal("29.400000"),
            timeout_seconds=5,
        )

    @override_settings(
        KASI2KASI_BASE_FARE="20.00",
        KASI2KASI_RATE_PER_KM="2.00",
        KASI2KASI_RATE_PER_MINUTE="1.00",
    )
    @patch("bookings.views.estimate_journey")
    def test_manual_locations_save_booking_without_estimate(
        self, mock_estimate
    ):
        data = self.data.copy()
        for field in (
            "pickup_latitude",
            "pickup_longitude",
            "destination_latitude",
            "destination_longitude",
        ):
            data.pop(field)

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 302)
        booking = TransportRequest.objects.get()
        self.assertIsNone(booking.estimated_fare)
        mock_estimate.assert_not_called()

    @override_settings(
        KASI2KASI_BASE_FARE=None,
        KASI2KASI_RATE_PER_KM="2.00",
        KASI2KASI_RATE_PER_MINUTE="1.00",
    )
    @patch("bookings.views.estimate_journey")
    def test_missing_pricing_saves_booking_without_estimate(
        self, mock_estimate
    ):
        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 302)
        booking = TransportRequest.objects.get()
        self.assertIsNone(booking.estimated_fare)
        mock_estimate.assert_not_called()

    @override_settings(
        KASI2KASI_BASE_FARE="20.00",
        KASI2KASI_RATE_PER_KM="2.00",
        KASI2KASI_RATE_PER_MINUTE="1.00",
    )
    @patch("bookings.views.estimate_journey")
    def test_routing_failure_does_not_block_booking(
        self, mock_estimate
    ):
        mock_estimate.side_effect = JourneyEstimationError(
            "Routing service unavailable"
        )

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 302)
        booking = TransportRequest.objects.get()
        self.assertIsNone(booking.estimated_fare)
        self.assertEqual(booking.status, TransportRequest.Status.PENDING)

    @override_settings(
        KASI2KASI_BASE_FARE="20.00",
        KASI2KASI_RATE_PER_KM="2.00",
        KASI2KASI_RATE_PER_MINUTE="1.00",
    )
    @patch("bookings.views.estimate_journey")
    def test_client_submitted_fares_are_ignored(self, mock_estimate):
        mock_estimate.return_value = self.estimate
        data = self.data.copy()
        data["estimated_fare"] = "1.00"
        data["proposed_fare"] = "2.00"
        data["agreed_fare"] = "3.00"

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 302)
        booking = TransportRequest.objects.get()
        self.assertEqual(booking.estimated_fare, Decimal("75.00"))
        self.assertIsNone(booking.proposed_fare)
        self.assertIsNone(booking.agreed_fare)

    @override_settings(
        KASI2KASI_BASE_FARE="invalid",
        KASI2KASI_RATE_PER_KM="2.00",
        KASI2KASI_RATE_PER_MINUTE="1.00",
    )
    @patch("bookings.views.estimate_journey")
    def test_invalid_pricing_does_not_block_booking(
        self, mock_estimate
    ):
        mock_estimate.return_value = self.estimate

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 302)
        booking = TransportRequest.objects.get()
        self.assertIsNone(booking.estimated_fare)
        self.assertIsNone(booking.proposed_fare)
        self.assertIsNone(booking.agreed_fare)