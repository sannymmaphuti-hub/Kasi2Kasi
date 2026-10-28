from decimal import Decimal

from django.test import SimpleTestCase

from bookings.pricing_policy import (
    FareChangeReason,
    PricingPolicy,
    PricingPolicyError,
    evaluate_fare_change,
)


class PricingPolicyTests(SimpleTestCase):
    def setUp(self):
        self.policy = PricingPolicy(
            allow_customer_requested_extra_stop=True,
            allow_customer_changed_destination=True,
            allow_eligible_waiting_charge=True,
        )

    def decide(self, **overrides):
        values = {
            "agreed_fare": "50.00",
            "requested_adjustment": "10.00",
            "reason": FareChangeReason.CUSTOMER_REQUESTED_EXTRA_STOP,
            "customer_approved": True,
            "disclosed_before_confirmation": True,
            "policy": self.policy,
        }
        values.update(overrides)
        return evaluate_fare_change(**values)

    def test_approved_disclosed_extra_stop_is_allowed(self):
        result = self.decide()
        self.assertTrue(result.allowed)
        self.assertEqual(result.final_fare, Decimal("60.00"))

    def test_ordinary_traffic_delay_cannot_raise_fare(self):
        result = self.decide(
            reason=FareChangeReason.ORDINARY_TRAFFIC_DELAY
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.final_fare, Decimal("50.00"))

    def test_driver_caused_delay_cannot_raise_fare(self):
        result = self.decide(
            reason=FareChangeReason.DRIVER_CAUSED_DELAY
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.final_fare, Decimal("50.00"))

    def test_undisclosed_adjustment_is_rejected(self):
        result = self.decide(disclosed_before_confirmation=False)
        self.assertFalse(result.allowed)
        self.assertEqual(result.final_fare, Decimal("50.00"))

    def test_unapproved_adjustment_is_rejected(self):
        result = self.decide(customer_approved=False)
        self.assertFalse(result.allowed)
        self.assertEqual(result.final_fare, Decimal("50.00"))

    def test_disabled_policy_rejects_adjustment(self):
        result = self.decide(policy=PricingPolicy())
        self.assertFalse(result.allowed)

    def test_negative_adjustment_is_rejected(self):
        with self.assertRaises(PricingPolicyError):
            self.decide(requested_adjustment="-5.00")

    def test_non_finite_adjustment_is_rejected(self):
        with self.assertRaises(PricingPolicyError):
            self.decide(requested_adjustment="NaN")

    def test_zero_adjustment_does_not_change_fare(self):
        result = self.decide(requested_adjustment="0")
        self.assertTrue(result.allowed)
        self.assertEqual(result.final_fare, Decimal("50.00"))

    def test_waiting_charge_requires_enabled_policy(self):
        result = self.decide(
            reason=FareChangeReason.ELIGIBLE_WAITING,
            policy=PricingPolicy(),
        )
        self.assertFalse(result.allowed)

    def test_invalid_agreed_fare_is_rejected(self):
        with self.assertRaises(PricingPolicyError):
            self.decide(agreed_fare="0")

    def test_destination_change_can_be_policy_controlled(self):
        result = self.decide(
            reason=FareChangeReason.CUSTOMER_CHANGED_DESTINATION
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.final_fare, Decimal("60.00"))

    def test_other_reason_is_not_authorised(self):
        result = self.decide(reason=FareChangeReason.OTHER)
        self.assertFalse(result.allowed)

    def test_invalid_approval_type_is_rejected(self):
        with self.assertRaises(PricingPolicyError):
            self.decide(customer_approved="yes")

    def test_unknown_reason_is_rejected(self):
        with self.assertRaises(PricingPolicyError):
            self.decide(reason="invented_reason")
