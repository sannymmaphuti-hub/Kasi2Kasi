"""Independent policy checks for proposed fare adjustments."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum


class PricingPolicyError(ValueError):
    """Raised when policy inputs are invalid."""


class FareChangeReason(str, Enum):
    CUSTOMER_REQUESTED_EXTRA_STOP = "customer_requested_extra_stop"
    CUSTOMER_CHANGED_DESTINATION = "customer_changed_destination"
    ELIGIBLE_WAITING = "eligible_waiting"
    ORDINARY_TRAFFIC_DELAY = "ordinary_traffic_delay"
    DRIVER_CAUSED_DELAY = "driver_caused_delay"
    OTHER = "other"


@dataclass(frozen=True)
class PricingPolicy:
    """Adjustment permissions. All are disabled by default."""

    allow_customer_requested_extra_stop: bool = False
    allow_customer_changed_destination: bool = False
    allow_eligible_waiting_charge: bool = False


@dataclass(frozen=True)
class FareChangeDecision:
    """Read-only result of evaluating a proposed fare adjustment."""

    allowed: bool
    reason: FareChangeReason
    original_fare: Decimal
    requested_adjustment: Decimal
    final_fare: Decimal
    explanation: str


def _money(value, field_name):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PricingPolicyError(
            f"{field_name} must be a valid decimal amount."
        ) from exc

    if not amount.is_finite():
        raise PricingPolicyError(f"{field_name} must be finite.")

    if amount < Decimal("0"):
        raise PricingPolicyError(f"{field_name} cannot be negative.")

    try:
        return amount.quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise PricingPolicyError(
            f"{field_name} is outside the supported money range."
        ) from exc


def evaluate_fare_change(
    *,
    agreed_fare,
    requested_adjustment,
    reason,
    customer_approved,
    disclosed_before_confirmation,
    policy,
):
    """Evaluate an adjustment without modifying a booking."""
    original = _money(agreed_fare, "agreed_fare")
    adjustment = _money(requested_adjustment, "requested_adjustment")

    if original <= Decimal("0"):
        raise PricingPolicyError("The agreed fare must be greater than zero.")

    if not isinstance(policy, PricingPolicy):
        raise PricingPolicyError("policy must be a PricingPolicy instance.")

    if not isinstance(customer_approved, bool):
        raise PricingPolicyError("customer_approved must be a boolean.")

    if not isinstance(disclosed_before_confirmation, bool):
        raise PricingPolicyError(
            "disclosed_before_confirmation must be a boolean."
        )

    try:
        change_reason = FareChangeReason(reason)
    except (ValueError, TypeError) as exc:
        raise PricingPolicyError(
            "The fare change reason is not recognised."
        ) from exc

    def deny(message):
        return FareChangeDecision(
            allowed=False,
            reason=change_reason,
            original_fare=original,
            requested_adjustment=adjustment,
            final_fare=original,
            explanation=message,
        )

    if change_reason == FareChangeReason.ORDINARY_TRAFFIC_DELAY:
        return deny(
            "Ordinary traffic delays cannot increase an agreed fare."
        )

    if change_reason == FareChangeReason.DRIVER_CAUSED_DELAY:
        return deny(
            "Driver-caused delays cannot justify an additional charge."
        )

    if change_reason == FareChangeReason.OTHER:
        return deny(
            "This adjustment reason is not authorised by the policy."
        )

    permissions = {
        FareChangeReason.CUSTOMER_REQUESTED_EXTRA_STOP:
            policy.allow_customer_requested_extra_stop,
        FareChangeReason.CUSTOMER_CHANGED_DESTINATION:
            policy.allow_customer_changed_destination,
        FareChangeReason.ELIGIBLE_WAITING:
            policy.allow_eligible_waiting_charge,
    }

    if not permissions[change_reason]:
        return deny(
            "The pricing policy does not permit this adjustment."
        )

    if adjustment == Decimal("0.00"):
        return FareChangeDecision(
            allowed=True,
            reason=change_reason,
            original_fare=original,
            requested_adjustment=adjustment,
            final_fare=original,
            explanation="No additional amount was requested.",
        )

    if not disclosed_before_confirmation:
        return deny(
            "The additional amount was not disclosed before confirmation."
        )

    if not customer_approved:
        return deny(
            "The customer has not approved the additional amount."
        )

    try:
        final_fare = (original + adjustment).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise PricingPolicyError(
            "The resulting fare is outside the supported money range."
        ) from exc

    return FareChangeDecision(
        allowed=True,
        reason=change_reason,
        original_fare=original,
        requested_adjustment=adjustment,
        final_fare=final_fare,
        explanation=(
            "The adjustment is permitted by policy and has been "
            "disclosed and approved."
        ),
    )
