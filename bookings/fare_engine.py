"""Transparent, provider-independent fare calculations for Kasi2Kasi."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional


CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class FareCalculationError(ValueError):
    """Raised when fare inputs or pricing rules are invalid."""


def _money(value, field_name):
    """Convert a monetary input to a finite Decimal."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise FareCalculationError(
            f"{field_name} must be a valid monetary amount."
        ) from None

    if not amount.is_finite():
        raise FareCalculationError(
            f"{field_name} must be a finite monetary amount."
        )

    if amount < 0:
        raise FareCalculationError(
            f"{field_name} cannot be negative."
        )

    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _non_negative_decimal(value, field_name):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise FareCalculationError(
            f"{field_name} must be a valid number."
        ) from None

    if not number.is_finite() or number < 0:
        raise FareCalculationError(
            f"{field_name} must be finite and non-negative."
        )

    return number


@dataclass(frozen=True)
class FareBreakdown:
    """Itemised estimated fare; amounts are expressed in currency units."""

    base_fare: Decimal
    distance_charge: Decimal
    time_charge: Decimal
    after_hours_charge: Decimal
    other_adjustments: Decimal
    discount: Decimal
    total: Decimal
    currency: str = "ZAR"


def calculate_fare(
    *,
    base_fare,
    distance_km,
    rate_per_km,
    estimated_minutes,
    rate_per_minute,
    after_hours_rate=Decimal("0"),
    is_after_hours=False,
    other_adjustments=Decimal("0"),
    discount=Decimal("0"),
    currency="ZAR",
):
    """
    Calculate a transparent fare estimate.

    Distance and duration must be estimates supplied by a trusted caller.
    This function does not fetch routes, determine operating hours, or
    change a booking's proposed or agreed fare.
    """
    base = _money(base_fare, "base_fare")
    per_km = _money(rate_per_km, "rate_per_km")
    per_minute = _money(rate_per_minute, "rate_per_minute")
    after_rate = _money(after_hours_rate, "after_hours_rate")
    adjustments = _money(other_adjustments, "other_adjustments")
    discount_amount = _money(discount, "discount")

    distance = _non_negative_decimal(distance_km, "distance_km")
    minutes = _non_negative_decimal(
        estimated_minutes, "estimated_minutes"
    )

    if not isinstance(is_after_hours, bool):
        raise FareCalculationError(
            "is_after_hours must be True or False."
        )

    if not isinstance(currency, str) or not currency.strip():
        raise FareCalculationError(
            "currency must be a non-empty string."
        )

    distance_charge = (distance * per_km).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    time_charge = (minutes * per_minute).quantize(
        CENT, rounding=ROUND_HALF_UP
    )

    after_hours_charge = (
        (base + distance_charge + time_charge) * after_rate
        if is_after_hours
        else ZERO
    ).quantize(CENT, rounding=ROUND_HALF_UP)

    subtotal = (
        base
        + distance_charge
        + time_charge
        + after_hours_charge
        + adjustments
    ).quantize(CENT, rounding=ROUND_HALF_UP)

    if discount_amount > subtotal:
        raise FareCalculationError(
            "discount cannot exceed the fare before discount."
        )

    total = (subtotal - discount_amount).quantize(
        CENT, rounding=ROUND_HALF_UP
    )

    if total <= ZERO:
        raise FareCalculationError(
            "The calculated fare must be greater than zero."
        )

    return FareBreakdown(
        base_fare=base,
        distance_charge=distance_charge,
        time_charge=time_charge,
        after_hours_charge=after_hours_charge,
        other_adjustments=adjustments,
        discount=discount_amount,
        total=total,
        currency=currency.strip().upper(),
    )
