"""Combine fare estimates and driver sustainability analysis."""

from dataclasses import dataclass
from decimal import Decimal

from bookings.driver_sustainability import (
    DriverSustainabilityBreakdown,
    calculate_driver_sustainability,
)
from bookings.fare_engine import (
    FareBreakdown,
    FareCalculationError,
    calculate_fare,
)


class PricingAdvisorError(ValueError):
    """Raised when pricing advice cannot be calculated safely."""


@dataclass(frozen=True)
class PricingAdvice:
    """Read-only analysis of a fare estimate and driver payout."""

    fare_estimate: FareBreakdown
    driver_analysis: DriverSustainabilityBreakdown
    estimated_operating_costs_covered: bool
    additional_payout_needed: Decimal


def advise_on_pricing(*, fare_inputs, sustainability_inputs):
    """
    Calculate a fare estimate and assess a separately supplied driver payout.

    This function does not choose production rates, set driver payouts,
    modify customer fares, or change booking records.
    """
    if not isinstance(fare_inputs, dict):
        raise PricingAdvisorError("fare_inputs must be a dictionary.")

    if not isinstance(sustainability_inputs, dict):
        raise PricingAdvisorError(
            "sustainability_inputs must be a dictionary."
        )

    try:
        fare = calculate_fare(**fare_inputs)
        driver = calculate_driver_sustainability(
            **sustainability_inputs
        )
    except (TypeError, ValueError) as exc:
        raise PricingAdvisorError(str(exc)) from exc

    if fare.currency != driver.currency:
        raise PricingAdvisorError(
            "Fare and driver payout calculations must use the same currency."
        )

    shortfall = max(
        Decimal("0.00"),
        driver.break_even_payout - driver.driver_payout,
    )

    return PricingAdvice(
        fare_estimate=fare,
        driver_analysis=driver,
        estimated_operating_costs_covered=(
            driver.driver_payout >= driver.break_even_payout
        ),
        additional_payout_needed=shortfall,
    )