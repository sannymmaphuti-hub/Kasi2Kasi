from decimal import Decimal

from django.test import SimpleTestCase

from bookings.journey_estimator import (
    JourneyEstimationError,
    estimate_journey,
)


class JourneyEstimatorTests(SimpleTestCase):
    def setUp(self):
        self.inputs = {
            "pickup_latitude": -23.8321,
            "pickup_longitude": 29.9975,
            "destination_latitude": -23.9000,
            "destination_longitude": 30.1000,
        }

    @staticmethod
    def successful_response(distance=12500, duration=1800):
        return {
            "code": "Ok",
            "routes": [
                {
                    "distance": distance,
                    "duration": duration,
                }
            ],
        }

    def fake_get(self, payload):
        calls = []

        def http_get(url, timeout):
            calls.append((url, timeout))
            return payload

        return http_get, calls

    def test_valid_route_returns_distance_and_duration(self):
        fake_get, _ = self.fake_get(self.successful_response())

        result = estimate_journey(
            **self.inputs,
            http_get=fake_get,
        )

        self.assertEqual(result.distance_km, Decimal("12.50"))
        self.assertEqual(result.duration_minutes, Decimal("30.00"))
        self.assertIn("OSRM", result.provider)

    def test_request_uses_longitude_before_latitude(self):
        fake_get, calls = self.fake_get(self.successful_response())

        estimate_journey(**self.inputs, http_get=fake_get)

        requested_url = calls[0][0]
        self.assertIn(
            "29.997500,-23.832100;30.100000,-23.900000",
            requested_url,
        )

    def test_request_uses_https(self):
        fake_get, calls = self.fake_get(self.successful_response())

        estimate_journey(**self.inputs, http_get=fake_get)

        self.assertTrue(calls[0][0].startswith("https://"))

    def test_request_uses_configured_timeout(self):
        fake_get, calls = self.fake_get(self.successful_response())

        estimate_journey(
            **self.inputs,
            timeout_seconds=7,
            http_get=fake_get,
        )

        self.assertEqual(calls[0][1], 7.0)

    def test_rejects_invalid_latitude(self):
        fake_get, _ = self.fake_get(self.successful_response())

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(
                **{**self.inputs, "pickup_latitude": 91},
                http_get=fake_get,
            )

    def test_rejects_invalid_longitude(self):
        fake_get, _ = self.fake_get(self.successful_response())

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(
                **{**self.inputs, "pickup_longitude": 181},
                http_get=fake_get,
            )

    def test_rejects_non_finite_coordinate(self):
        fake_get, _ = self.fake_get(self.successful_response())

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(
                **{**self.inputs, "pickup_latitude": "NaN"},
                http_get=fake_get,
            )

    def test_rejects_identical_coordinates(self):
        fake_get, _ = self.fake_get(self.successful_response())

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(
                **{
                    **self.inputs,
                    "destination_latitude": self.inputs["pickup_latitude"],
                    "destination_longitude": self.inputs["pickup_longitude"],
                },
                http_get=fake_get,
            )

    def test_rejects_insecure_routing_url(self):
        fake_get, _ = self.fake_get(self.successful_response())

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(
                **self.inputs,
                routing_url="http://example.com/route/v1/driving",
                http_get=fake_get,
            )

    def test_rejects_non_positive_timeout(self):
        fake_get, _ = self.fake_get(self.successful_response())

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(
                **self.inputs,
                timeout_seconds=0,
                http_get=fake_get,
            )

    def test_rejects_route_not_found(self):
        fake_get, _ = self.fake_get({
            "code": "NoRoute",
            "routes": [],
        })

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(**self.inputs, http_get=fake_get)

    def test_rejects_missing_routes(self):
        fake_get, _ = self.fake_get({
            "code": "Ok",
            "routes": [],
        })

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(**self.inputs, http_get=fake_get)

    def test_rejects_invalid_distance(self):
        fake_get, _ = self.fake_get(
            self.successful_response(distance=float("nan"))
        )

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(**self.inputs, http_get=fake_get)

    def test_rejects_zero_duration(self):
        fake_get, _ = self.fake_get(
            self.successful_response(duration=0)
        )

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(**self.inputs, http_get=fake_get)

    def test_converts_network_failure_to_domain_error(self):
        def failing_get(url, timeout):
            raise TimeoutError("Simulated routing timeout")

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(**self.inputs, http_get=failing_get)

    def test_rejects_non_dictionary_response(self):
        fake_get, _ = self.fake_get([])

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(**self.inputs, http_get=fake_get)
    def test_route_distance_uses_half_up_rounding(self):
        fake_get, _ = self.fake_get(
            self.successful_response(distance=10005, duration=1200)
        )

        result = estimate_journey(
            **self.inputs,
            http_get=fake_get,
        )

        self.assertEqual(result.distance_km, Decimal("10.01"))
        self.assertEqual(result.duration_minutes, Decimal("20.00"))

    def test_route_duration_uses_half_up_rounding(self):
        fake_get, _ = self.fake_get(
            self.successful_response(distance=10000, duration=1203)
        )

        result = estimate_journey(
            **self.inputs,
            http_get=fake_get,
        )

        self.assertEqual(result.duration_minutes, Decimal("20.05"))

    def test_rejects_boolean_route_distance(self):
        fake_get, _ = self.fake_get(
            self.successful_response(distance=True)
        )

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(**self.inputs, http_get=fake_get)

    def test_rejects_infinite_route_duration(self):
        fake_get, _ = self.fake_get(
            self.successful_response(duration=float("inf"))
        )

        with self.assertRaises(JourneyEstimationError):
            estimate_journey(**self.inputs, http_get=fake_get)
