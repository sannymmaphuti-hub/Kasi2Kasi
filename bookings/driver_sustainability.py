"""Internal operating-cost estimates for Kasi2Kasi drivers."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CENT = Decimal("0.01")
ZERO = Decimal("0.00")
SIXTY = Decimal("60")


class SustainabilityCalculationError(ValueError):
    """Raised when sustainability calculation inputs are invalid."""


def _decimal(value, field_name):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise SustainabilityCalculationError(
            f"{field_name} must be a valid number."
        ) from None

    if not result.is_finite():
        raise SustainabilityCalculationError(
            f"{field_name} must be finite."
        )

    if result < 0:
        raise SustainabilityCalculationError(
            f"{field_name} cannot be negative."
        )

    return result


def _money(value, field_name):
    return _decimal(value, field_name).quantize(
        CENT,
        rounding=ROUND_HALF_UP,
    )


def _rounded_money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class DriverSustainabilityBreakdown:
    """Estimated journey economics; this is not an accounting statement."""

    driver_payout: Decimal
    pickup_distance_km: Decimal
    passenger_distance_km: Decimal
    return_distance_km: Decimal
    total_operating_distance_km: Decimal
    estimated_fuel_litres: Decimal
    fuel_cost: Decimal
    maintenance_reserve: Decimal
    other_operating_costs: Decimal
    total_estimated_operating_cost: Decimal
    estimated_net_earnings: Decimal
    break_even_payout: Decimal
    committed_time_minutes: Decimal
    estimated_net_earnings_per_hour: Decimal
    currency: str = "ZAR"


def calculate_driver_sustainability(
    *,
    driver_payout,
    pickup_distance_km,
    passenger_distance_km,
    return_distance_km,
    fuel_consumption_l_per_100km,
    fuel_price_per_litre,
    maintenance_reserve_per_km,
    other_operating_costs=Decimal("0"),
    committed_time_minutes,
    currency="ZAR",
):
    """
    Estimate driver operating costs and earnings.

    Distances must be estimated road distances supplied by the caller.
    Return distance is included in operating costs but is not automatically
    added to the customer's fare.

    This function does not set prices, fetch routes, or modify bookings.
    """
    payout = _money(driver_payout, "driver_payout")
    other_costs = _money(other_operating_costs, "other_operating_costs")

    pickup_distance = _decimal(
        pickup_distance_km, "pickup_distance_km"
    )
    passenger_distance = _decimal(
        passenger_distance_km, "passenger_distance_km"
    )
    return_distance = _decimal(
        return_distance_km, "return_distance_km"
    )

    fuel_consumption = _decimal(
        fuel_consumption_l_per_100km,
        "fuel_consumption_l_per_100km",
    )
    fuel_price = _money(fuel_price_per_litre, "fuel_price_per_litre")
    maintenance_rate = _money(
        maintenance_reserve_per_km,
        "maintenance_reserve_per_km",
    )
    committed_minutes = _decimal(
        committed_time_minutes, "committed_time_minutes"
    )

    if committed_minutes <= 0:
        raise SustainabilityCalculationError(
            "committed_time_minutes must be greater than zero."
        )

    if not isinstance(currency, str) or not currency.strip():
        raise SustainabilityCalculationError(
            "currency must be a non-empty string."
        )

    total_distance = (
        pickup_distance + passenger_distance + return_distance
    )

    fuel_litres = (
        total_distance * fuel_consumption / Decimal("100")
    )

    fuel_cost = _rounded_money(fuel_litres * fuel_price)
    maintenance_cost = _rounded_money(
        total_distance * maintenance_rate
    )

    total_cost = _rounded_money(
        fuel_cost + maintenance_cost + other_costs
    )

    net_earnings = _rounded_money(payout - total_cost)

    net_per_hour = _rounded_money(
        net_earnings * SIXTY / committed_minutes
    )

    return DriverSustainabilityBreakdown(
        driver_payout=payout,
        pickup_distance_km=pickup_distance,
        passenger_distance_km=passenger_distance,
        return_distance_km=return_distance,
        total_operating_distance_km=total_distance,
        estimated_fuel_litres=fuel_litres,
        fuel_cost=fuel_cost,
        maintenance_reserve=maintenance_cost,
        other_operating_costs=other_costs,
        total_estimated_operating_cost=total_cost,
        estimated_net_earnings=net_earnings,
        break_even_payout=total_cost,
        committed_time_minutes=committed_minutes,
        estimated_net_earnings_per_hour=net_per_hour,
        currency=currency.strip().upper(),
    )
