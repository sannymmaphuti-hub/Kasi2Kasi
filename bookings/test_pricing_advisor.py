from decimal import Decimal

from django.test import SimpleTestCase

from bookings.pricing_advisor import (
    PricingAdvisorError,
    advise_on_pricing,
)


class PricingAdvisorTests(SimpleTestCase):
    def setUp(self):
        self.fare_inputs = {
            "base_fare": "10.00",
            "distance_km": "5",
            "rate_per_km": "2.00",
            "estimated_minutes": "10",
            "rate_per_minute": "0.50",
        }

        self.sustainability_inputs = {
            "driver_payout": "100.00",
            "pickup_distance_km": "5",
            "passenger_distance_km": "20",
            "return_distance_km": "10",
            "fuel_consumption_l_per_100km": "8",
            "fuel_price_per_litre": "25.00",
            "maintenance_reserve_per_km": "1.00",
            "other_operating_costs": "5.00",
            "committed_time_minutes": "90",
        }

    def test_combines_both_calculators(self):
        advice = advise_on_pricing(
            fare_inputs=self.fare_inputs,
            sustainability_inputs=self.sustainability_inputs,
        )

        self.assertEqual(
            advice.fare_estimate.total,
            Decimal("25.00"),
        )
        self.assertEqual(
            advice.driver_analysis.driver_payout,
            Decimal("100.00"),
        )

    def test_reports_operating_cost_shortfall(self):
        advice = advise_on_pricing(
            fare_inputs=self.fare_inputs,
            sustainability_inputs=self.sustainability_inputs,
        )

        self.assertFalse(
            advice.estimated_operating_costs_covered
        )
        self.assertEqual(
            advice.additional_payout_needed,
            Decimal("10.00"),
        )

    def test_reports_when_operating_costs_are_covered(self):
        inputs = {
            **self.sustainability_inputs,
            "driver_payout": "150.00",
        }

        advice = advise_on_pricing(
            fare_inputs=self.fare_inputs,
            sustainability_inputs=inputs,
        )

        self.assertTrue(
            advice.estimated_operating_costs_covered
        )
        self.assertEqual(
            advice.additional_payout_needed,
            Decimal("0.00"),
        )

    def test_currency_mismatch_is_rejected(self):
        inputs = {
            **self.sustainability_inputs,
            "currency": "USD",
        }

        with self.assertRaises(PricingAdvisorError):
            advise_on_pricing(
                fare_inputs=self.fare_inputs,
                sustainability_inputs=inputs,
            )

    def test_invalid_fare_input_is_rejected(self):
        inputs = {
            **self.fare_inputs,
            "distance_km": "-5",
        }

        with self.assertRaises(PricingAdvisorError):
            advise_on_pricing(
                fare_inputs=inputs,
                sustainability_inputs=self.sustainability_inputs,
            )

    def test_missing_required_input_is_rejected(self):
        inputs = {
            "driver_payout": "100.00",
        }

        with self.assertRaises(PricingAdvisorError):
            advise_on_pricing(
                fare_inputs=self.fare_inputs,
                sustainability_inputs=inputs,
            )

    def test_invalid_input_container_is_rejected(self):
        with self.assertRaises(PricingAdvisorError):
            advise_on_pricing(
                fare_inputs=[],
                sustainability_inputs=self.sustainability_inputs,
            )