from decimal import Decimal

from django.test import SimpleTestCase

from bookings.fare_engine import (
    FareCalculationError,
    calculate_fare,
)


class FairFareCalculationTests(SimpleTestCase):
    def setUp(self):
        self.standard_inputs = {
            "base_fare": "10.00",
            "distance_km": "5",
            "rate_per_km": "2.00",
            "estimated_minutes": "10",
            "rate_per_minute": "0.50",
        }

    def test_calculates_itemised_standard_fare(self):
        result = calculate_fare(**self.standard_inputs)

        self.assertEqual(result.base_fare, Decimal("10.00"))
        self.assertEqual(result.distance_charge, Decimal("10.00"))
        self.assertEqual(result.time_charge, Decimal("5.00"))
        self.assertEqual(result.after_hours_charge, Decimal("0.00"))
        self.assertEqual(result.total, Decimal("25.00"))
        self.assertEqual(result.currency, "ZAR")

    def test_after_hours_charge_is_only_applied_when_enabled(self):
        result = calculate_fare(
            **self.standard_inputs,
            after_hours_rate="0.10",
            is_after_hours=True,
        )

        self.assertEqual(result.after_hours_charge, Decimal("2.50"))
        self.assertEqual(result.total, Decimal("27.50"))

    def test_no_after_hours_charge_when_disabled(self):
        result = calculate_fare(
            **self.standard_inputs,
            after_hours_rate="0.10",
            is_after_hours=False,
        )

        self.assertEqual(result.after_hours_charge, Decimal("0.00"))
        self.assertEqual(result.total, Decimal("25.00"))

    def test_applies_adjustments_and_discount_transparently(self):
        result = calculate_fare(
            **self.standard_inputs,
            other_adjustments="3.00",
            discount="2.00",
        )

        self.assertEqual(result.other_adjustments, Decimal("3.00"))
        self.assertEqual(result.discount, Decimal("2.00"))
        self.assertEqual(result.total, Decimal("26.00"))

    def test_rounds_money_to_two_decimal_places(self):
        result = calculate_fare(
            base_fare="10.005",
            distance_km="0",
            rate_per_km="1",
            estimated_minutes="0",
            rate_per_minute="1",
        )

        self.assertEqual(result.base_fare, Decimal("10.01"))
        self.assertEqual(result.total, Decimal("10.01"))

    def test_rejects_negative_distance(self):
        with self.assertRaises(FareCalculationError):
            calculate_fare(
                **{**self.standard_inputs, "distance_km": "-1"}
            )

    def test_rejects_non_finite_monetary_input(self):
        with self.assertRaises(FareCalculationError):
            calculate_fare(
                **{**self.standard_inputs, "base_fare": "NaN"}
            )

    def test_rejects_discount_greater_than_subtotal(self):
        with self.assertRaises(FareCalculationError):
            calculate_fare(
                **self.standard_inputs,
                discount="1000",
            )

    def test_rejects_zero_total(self):
        with self.assertRaises(FareCalculationError):
            calculate_fare(
                base_fare="0",
                distance_km="0",
                rate_per_km="0",
                estimated_minutes="0",
                rate_per_minute="0",
            )

    def test_rejects_non_boolean_after_hours_flag(self):
        with self.assertRaises(FareCalculationError):
            calculate_fare(
                **self.standard_inputs,
                is_after_hours="yes",
            )

    def test_rejects_invalid_currency(self):
        with self.assertRaises(FareCalculationError):
            calculate_fare(
                **self.standard_inputs,
                currency=" ",
            )
