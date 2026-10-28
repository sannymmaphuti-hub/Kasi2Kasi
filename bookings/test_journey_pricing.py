from decimal import Decimal
from django.test import SimpleTestCase

from bookings.journey_pricing import (
    JourneyPricingError,
    estimate_journey_pricing,
)


class JourneyPricingIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.route_payload = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 12500,
                    "duration": 1800,
                }
            ],
        }

        self.fare_inputs = {
            "base_fare": "10.00",
            "rate_per_km": "2.00",
            "rate_per_minute": "0.50",
        }

        self.coordinates = {
            "pickup_latitude": -23.8321,
            "pickup_longitude": 29.9975,
            "destination_latitude": -23.9000,
            "destination_longitude": 30.1000,
        }

    def fake_http_get(self, *args, **kwargs):
        return self.route_payload

    def estimate(self, **overrides):
        arguments = {
            **self.coordinates,
            "fare_inputs": dict(self.fare_inputs),
            "http_get": self.fake_http_get,
        }
        arguments.update(overrides)
        return estimate_journey_pricing(**arguments)

    def test_road_distance_and_time_feed_into_fare(self):
        result = self.estimate()

        self.assertEqual(result.journey.distance_km, Decimal("12.50"))
        self.assertEqual(result.journey.duration_minutes, Decimal("30.00"))
        self.assertEqual(result.fare.total, Decimal("50.00"))
        self.assertIsNone(result.pricing_advice)

    def test_estimator_receives_the_injected_routing_function(self):
        calls = []

        def recording_http_get(*args, **kwargs):
            calls.append((args, kwargs))
            return self.route_payload

        result = self.estimate(http_get=recording_http_get)

        self.assertEqual(len(calls), 1)
        self.assertIsNotNone(result.journey)

    def test_rejects_non_dictionary_fare_inputs(self):
        with self.assertRaises(JourneyPricingError):
            self.estimate(fare_inputs=["not", "a", "dictionary"])

    def test_rejects_user_supplied_distance(self):
        fare_inputs = dict(self.fare_inputs)
        fare_inputs["distance_km"] = "5.00"

        with self.assertRaises(JourneyPricingError):
            self.estimate(fare_inputs=fare_inputs)

    def test_rejects_user_supplied_estimated_minutes(self):
        fare_inputs = dict(self.fare_inputs)
        fare_inputs["estimated_minutes"] = "10"

        with self.assertRaises(JourneyPricingError):
            self.estimate(fare_inputs=fare_inputs)

    def test_wraps_invalid_fare_inputs(self):
        with self.assertRaises(JourneyPricingError):
            self.estimate(
                fare_inputs={
                    "base_fare": "not-a-number",
                    "rate_per_km": "2.00",
                    "rate_per_minute": "0.50",
                }
            )

    def test_wraps_routing_failure(self):
        def failed_http_get(*args, **kwargs):
            raise OSError("Simulated routing service failure")

        with self.assertRaises(JourneyPricingError):
            self.estimate(http_get=failed_http_get)

    def test_rejects_non_dictionary_sustainability_inputs(self):
        with self.assertRaises(JourneyPricingError):
            self.estimate(sustainability_inputs=["invalid"])

    def test_rejects_user_supplied_passenger_distance(self):
        sustainability_inputs = {
            "driver_payout": "50.00",
            "passenger_distance_km": "99.00",
        }

        with self.assertRaises(JourneyPricingError):
            self.estimate(sustainability_inputs=sustainability_inputs)

    def test_rejects_user_supplied_committed_time(self):
        sustainability_inputs = {
            "driver_payout": "50.00",
            "committed_time_minutes": "99",
        }

        with self.assertRaises(JourneyPricingError):
            self.estimate(sustainability_inputs=sustainability_inputs)

    def test_sustainability_uses_the_estimated_journey(self):
        sustainability_inputs = {
            "driver_payout": "50.00",
            "pickup_distance_km": "3.00",
            "return_distance_km": "4.00",
            "fuel_consumption_l_per_100km": "8.00",
            "fuel_price_per_litre": "22.00",
            "maintenance_reserve_per_km": "1.00",
            "other_operating_costs": "0.00",
        }

        result = self.estimate(
            sustainability_inputs=sustainability_inputs
        )

        self.assertIsNotNone(result.pricing_advice)
        self.assertEqual(
            result.pricing_advice.fare_estimate.total,
            Decimal("50.00"),
        )
        self.assertEqual(
            result.pricing_advice.driver_analysis.passenger_distance_km,
            Decimal("12.50"),
        )
        self.assertEqual(
            result.pricing_advice.driver_analysis.committed_time_minutes,
            Decimal("30.00"),
        )

    def test_rejects_currency_mismatch_in_sustainability_analysis(self):
        sustainability_inputs = {
            "driver_payout": "50.00",
            "pickup_distance_km": "3.00",
            "return_distance_km": "4.00",
            "fuel_consumption_l_per_100km": "8.00",
            "fuel_price_per_litre": "22.00",
            "maintenance_reserve_per_km": "1.00",
            "other_operating_costs": "0.00",
            "currency": "ZAR",
        }

        fare_inputs = dict(self.fare_inputs)
        fare_inputs["currency"] = "EUR"

        with self.assertRaises(JourneyPricingError):
            self.estimate(
                fare_inputs=fare_inputs,
                sustainability_inputs=sustainability_inputs,
            )

