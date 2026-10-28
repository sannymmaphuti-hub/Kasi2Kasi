from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from bookings.models import TransportRequest


class DriverFareProposalTests(TestCase):
    def setUp(self):
        self.driver = self.make_user(
            "fare_proposal_driver",
            UserProfile.Role.DRIVER,
            UserProfile.DriverStatus.APPROVED,
        )
        self.other_driver = self.make_user(
            "fare_proposal_other_driver",
            UserProfile.Role.DRIVER,
            UserProfile.DriverStatus.APPROVED,
        )
        self.customer = self.make_user(
            "fare_proposal_customer",
            UserProfile.Role.CUSTOMER,
            UserProfile.DriverStatus.NOT_APPLICABLE,
        )
        self.ride = self.make_ride(self.driver)

    def make_user(self, username, role, driver_status):
        user = User.objects.create_user(
            username=username,
            password="KasiTest!2026Secure",
        )
        UserProfile.objects.create(
            user=user,
            role=role,
            driver_status=driver_status,
        )
        return user

    def make_ride(self, driver, proposed_fare=None, status=None):
        values = {
            "assigned_driver": driver,
            "customer": self.customer,
            "customer_name": "Test Passenger",
            "contact_number": "0712345678",
            "pickup_location": "Bochum",
            "destination": "Polokwane",
            "travel_datetime": timezone.now() + timedelta(days=1),
            "passenger_count": 1,
            "proposed_fare": proposed_fare,
        }
        if status is not None:
            values["status"] = status
        return TransportRequest.objects.create(**values)

    def test_driver_can_propose_valid_fare(self):
        self.client.force_login(self.driver)

        response = self.client.post(
            reverse("propose_assigned_ride_fare", args=[self.ride.pk]),
            {"proposed_fare": "175.50"},
        )

        self.assertRedirects(response, reverse("assigned_driver_rides"))
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.proposed_fare, Decimal("175.50"))
        self.assertEqual(self.ride.status, TransportRequest.Status.PENDING)

    def test_invalid_fares_are_rejected(self):
        self.client.force_login(self.driver)

        for value in ("", "abc", "0", "-10", "NaN", "Infinity"):
            with self.subTest(proposed_fare=value):
                self.ride.proposed_fare = None
                self.ride.save(update_fields=["proposed_fare"])

                response = self.client.post(
                    reverse("propose_assigned_ride_fare", args=[self.ride.pk]),
                    {"proposed_fare": value},
                )

                self.assertRedirects(
                    response,
                    reverse("assigned_driver_rides"),
                )
                self.ride.refresh_from_db()
                self.assertIsNone(self.ride.proposed_fare)
                self.assertEqual(
                    self.ride.status,
                    TransportRequest.Status.PENDING,
                )

    def test_driver_cannot_propose_fare_for_another_drivers_ride(self):
        other_ride = self.make_ride(self.other_driver)
        self.client.force_login(self.driver)

        response = self.client.post(
            reverse("propose_assigned_ride_fare", args=[other_ride.pk]),
            {"proposed_fare": "200.00"},
        )

        self.assertEqual(response.status_code, 404)
        other_ride.refresh_from_db()
        self.assertIsNone(other_ride.proposed_fare)

    def test_fare_cannot_be_changed_after_ride_is_accepted(self):
        self.ride.proposed_fare = Decimal("150.00")
        self.ride.status = TransportRequest.Status.ACCEPTED
        self.ride.save(update_fields=["proposed_fare", "status"])
        self.client.force_login(self.driver)

        response = self.client.post(
            reverse("propose_assigned_ride_fare", args=[self.ride.pk]),
            {"proposed_fare": "250.00"},
        )

        self.assertRedirects(response, reverse("assigned_driver_rides"))
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.proposed_fare, Decimal("150.00"))

    def test_get_request_cannot_propose_fare(self):
        self.client.force_login(self.driver)

        response = self.client.get(
            reverse("propose_assigned_ride_fare", args=[self.ride.pk]),
        )

        self.assertEqual(response.status_code, 405)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.proposed_fare)

    def test_driver_cannot_accept_ride_without_fare(self):
        self.ride.proposed_fare = None
        self.ride.save(update_fields=["proposed_fare"])
        self.client.force_login(self.driver)

        response = self.client.post(
            reverse("accept_assigned_ride", args=[self.ride.pk]),
        )

        self.assertRedirects(response, reverse("assigned_driver_rides"))
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, TransportRequest.Status.PENDING)
