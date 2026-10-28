from decimal import Decimal

from django.test import SimpleTestCase

from bookings.driver_sustainability import (
    SustainabilityCalculationError,
    calculate_driver_sustainability,
)


class DriverSustainabilityTests(SimpleTestCase):
    def setUp(self):
        self.inputs = {
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

    def test_calculates_total_operating_distance(self):
        result = calculate_driver_sustainability(**self.inputs)

        self.assertEqual(
            result.total_operating_distance_km,
            Decimal("35"),
        )

    def test_calculates_fuel_consumption_and_cost(self):
        result = calculate_driver_sustainability(**self.inputs)

        # 35 km * 8 litres / 100 km = 2.8 litres.
        self.assertEqual(
            result.estimated_fuel_litres,
            Decimal("2.8"),
        )
        self.assertEqual(result.fuel_cost, Decimal("70.00"))

    def test_calculates_operating_costs_and_net_earnings(self):
        result = calculate_driver_sustainability(**self.inputs)

        # Fuel 70 + maintenance 35 + other costs 5 = 110.
        self.assertEqual(
            result.total_estimated_operating_cost,
            Decimal("110.00"),
        )
        self.assertEqual(result.break_even_payout, Decimal("110.00"))
        self.assertEqual(
            result.estimated_net_earnings,
            Decimal("-10.00"),
        )

    def test_calculates_net_earnings_per_hour(self):
        result = calculate_driver_sustainability(**self.inputs)

        # -10 net earnings over 90 minutes = -6.67 per hour.
        self.assertEqual(
            result.estimated_net_earnings_per_hour,
            Decimal("-6.67"),
        )

    def test_return_distance_is_counted_in_operating_costs(self):
        with_return = calculate_driver_sustainability(
            **self.inputs
        )

        without_return = calculate_driver_sustainability(
            **{**self.inputs, "return_distance_km": "0"}
        )

        self.assertGreater(
            with_return.total_estimated_operating_cost,
            without_return.total_estimated_operating_cost,
        )

    def test_return_distance_does_not_change_driver_payout(self):
        result = calculate_driver_sustainability(**self.inputs)

        self.assertEqual(result.driver_payout, Decimal("100.00"))

    def test_zero_fuel_consumption_is_supported(self):
        result = calculate_driver_sustainability(
            **{
                **self.inputs,
                "fuel_consumption_l_per_100km": "0",
            }
        )

        self.assertEqual(result.fuel_cost, Decimal("0.00"))

    def test_rejects_negative_distance(self):
        with self.assertRaises(SustainabilityCalculationError):
            calculate_driver_sustainability(
                **{**self.inputs, "pickup_distance_km": "-1"}
            )

    def test_rejects_non_finite_input(self):
        with self.assertRaises(SustainabilityCalculationError):
            calculate_driver_sustainability(
                **{**self.inputs, "fuel_price_per_litre": "NaN"}
            )

    def test_rejects_zero_committed_time(self):
        with self.assertRaises(SustainabilityCalculationError):
            calculate_driver_sustainability(
                **{**self.inputs, "committed_time_minutes": "0"}
            )

    def test_rejects_negative_payout(self):
        with self.assertRaises(SustainabilityCalculationError):
            calculate_driver_sustainability(
                **{**self.inputs, "driver_payout": "-10"}
            )

    def test_rejects_empty_currency(self):
        with self.assertRaises(SustainabilityCalculationError):
            calculate_driver_sustainability(
                **{**self.inputs, "currency": " "}
            )