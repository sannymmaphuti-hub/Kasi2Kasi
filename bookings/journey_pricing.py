"""Read-only integration between journey estimation and pricing."""

from dataclasses import dataclass
from typing import Optional

from bookings.fare_engine import FareBreakdown, calculate_fare
from bookings.journey_estimator import (
    JourneyEstimate,
    JourneyEstimationError,
    estimate_journey,
)
from bookings.pricing_advisor import (
    PricingAdvice,
    advise_on_pricing,
)


class JourneyPricingError(ValueError):
    """Raised when journey-based pricing cannot be calculated safely."""


@dataclass(frozen=True)
class JourneyPricingResult:
    """Journey estimate and associated fare calculation."""

    journey: JourneyEstimate
    fare: FareBreakdown
    pricing_advice: Optional[PricingAdvice] = None


def estimate_journey_pricing(
    *,
    pickup_latitude,
    pickup_longitude,
    destination_latitude,
    destination_longitude,
    fare_inputs,
    sustainability_inputs=None,
    routing_url=None,
    timeout_seconds=20,
    http_get=None,
):
    """Estimate a journey fare without modifying a booking.

    Fare inputs must contain the rates and adjustments accepted by the
    Fare Engine, except distance_km and estimated_minutes. Those two
    values are derived exclusively from the road journey estimate.

    If sustainability_inputs is supplied, it must contain the driver
    payout, pickup distance, return distance, vehicle operating-cost
    assumptions, and any other required sustainability inputs.
    Passenger distance and committed journey time are derived from the
    same journey estimate used for the fare.

    This function does not create or modify booking records.
    """
    if not isinstance(fare_inputs, dict):
        raise JourneyPricingError("fare_inputs must be a dictionary.")

    if "distance_km" in fare_inputs:
        raise JourneyPricingError(
            "distance_km is supplied by the journey estimator, not fare_inputs."
        )

    if "estimated_minutes" in fare_inputs:
        raise JourneyPricingError(
            "estimated_minutes is supplied by the journey estimator, not fare_inputs."
        )

    if sustainability_inputs is not None:
        if not isinstance(sustainability_inputs, dict):
            raise JourneyPricingError(
                "sustainability_inputs must be a dictionary when supplied."
            )

        if "passenger_distance_km" in sustainability_inputs:
            raise JourneyPricingError(
                "passenger_distance_km is derived from the journey estimate."
            )

        if "committed_time_minutes" in sustainability_inputs:
            raise JourneyPricingError(
                "committed_time_minutes is derived from the journey estimate."
            )

    try:
        journey_arguments = {
            "pickup_latitude": pickup_latitude,
            "pickup_longitude": pickup_longitude,
            "destination_latitude": destination_latitude,
            "destination_longitude": destination_longitude,
            "timeout_seconds": timeout_seconds,
        }

        if routing_url is not None:
            journey_arguments["routing_url"] = routing_url

        if http_get is not None:
            journey_arguments["http_get"] = http_get

        journey = estimate_journey(**journey_arguments)

        resolved_fare_inputs = dict(fare_inputs)
        resolved_fare_inputs["distance_km"] = journey.distance_km
        resolved_fare_inputs["estimated_minutes"] = journey.duration_minutes

        if sustainability_inputs is None:
            fare = calculate_fare(**resolved_fare_inputs)

            return JourneyPricingResult(
                journey=journey,
                fare=fare,
                pricing_advice=None,
            )

        resolved_sustainability_inputs = dict(sustainability_inputs)
        resolved_sustainability_inputs["passenger_distance_km"] = (
            journey.distance_km
        )
        resolved_sustainability_inputs["committed_time_minutes"] = (
            journey.duration_minutes
        )

        advice = advise_on_pricing(
            fare_inputs=resolved_fare_inputs,
            sustainability_inputs=resolved_sustainability_inputs,
        )

        return JourneyPricingResult(
            journey=journey,
            fare=advice.fare_estimate,
            pricing_advice=advice,
        )

    except (JourneyEstimationError, TypeError, ValueError) as exc:
        raise JourneyPricingError(str(exc)) from exc
