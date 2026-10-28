import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from bookings.models import TransportRequest


class ReverseGeocodeAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user(
            username="reversecustomer",
            password="Customer!Secure2026",
        )
        UserProfile.objects.create(user=self.customer, role=UserProfile.Role.CUSTOMER)
        self.driver = User.objects.create_user(
            username="reversedriver",
            password="Driver!Secure2026",
        )
        UserProfile.objects.create(user=self.driver, role=UserProfile.Role.DRIVER)
        self.url = reverse("reverse_geocode_api")

    def post_json(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_anonymous_user_redirects_to_login(self):
        response = self.post_json({"latitude": -23.0, "longitude": 29.0})
        self.assertEqual(response.status_code, 302)

    @patch("bookings.views.reverse_geocode", return_value={
        "address": "Example locality, Limpopo, South Africa",
        "provider": "OpenStreetMap Nominatim",
        "attribution": "┬⌐ OpenStreetMap contributors",
    })
    def test_customer_receives_address(self, mock_geocode):
        self.client.force_login(self.customer)
        response = self.post_json({"latitude": -23.0, "longitude": 29.0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["address"], "Example locality, Limpopo, South Africa")
        mock_geocode.assert_called_once()

    def test_driver_is_forbidden(self):
        self.client.force_login(self.driver)
        response = self.post_json({"latitude": -23.0, "longitude": 29.0})
        self.assertEqual(response.status_code, 403)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_invalid_json_is_rejected(self):
        self.client.force_login(self.customer)
        response = self.client.post(self.url, data="{invalid", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_json_array_is_rejected(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.post_json([-23, 29]).status_code, 400)

    def test_missing_latitude_is_rejected(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.post_json({"longitude": 29}).status_code, 400)

    def test_boolean_coordinate_is_rejected(self):
        self.client.force_login(self.customer)
        response = self.post_json({"latitude": True, "longitude": 29})
        self.assertEqual(response.status_code, 400)

    def test_out_of_range_coordinate_is_rejected(self):
        self.client.force_login(self.customer)
        response = self.post_json({"latitude": -91, "longitude": 29})
        self.assertEqual(response.status_code, 400)

    @patch("bookings.views.reverse_geocode", return_value=None)
    def test_unavailable_address_returns_fallback(self, mock_geocode):
        self.client.force_login(self.customer)
        response = self.post_json({"latitude": -23.0, "longitude": 29.0})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["address"])
        self.assertIn("attribution", response.json())
        mock_geocode.assert_called_once()

    @patch("bookings.views.reverse_geocode", side_effect=RuntimeError("Provider unavailable"))
    def test_provider_error_does_not_crash_api(self, mock_geocode):
        self.client.force_login(self.customer)
        response = self.post_json({"latitude": -23.0, "longitude": 29.0})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["address"])

    @patch("bookings.views.reverse_geocode", return_value={
        "address": "Example place",
        "provider": "OpenStreetMap Nominatim",
        "attribution": "┬⌐ OpenStreetMap contributors",
    })
    def test_geocoding_does_not_create_booking(self, mock_geocode):
        self.client.force_login(self.customer)
        before = TransportRequest.objects.count()
        response = self.post_json({"latitude": -23.0, "longitude": 29.0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TransportRequest.objects.count(), before)
