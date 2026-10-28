from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from bookings.models import TransportRequest


User = get_user_model()


class CustomerDashboardOverviewTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer_overview",
            password="Customer!Secure2026",
            first_name="Dashboard",
        )
        UserProfile.objects.create(
            user=self.customer,
            role=UserProfile.Role.CUSTOMER,
        )
        self.client.force_login(self.customer)
        self.url = reverse("account_dashboard")

    def create_ride(
        self,
        *,
        customer=None,
        status=TransportRequest.Status.PENDING,
        pickup="Soweto",
        destination="Johannesburg",
        proposed_fare=None,
        agreed_fare=None,
        days_ahead=2,
    ):
        return TransportRequest.objects.create(
            customer=customer or self.customer,
            customer_name="Dashboard Customer",
            contact_number="0712345678",
            pickup_location=pickup,
            destination=destination,
            travel_datetime=timezone.now() + timedelta(days=days_ahead),
            passenger_count=1,
            status=status,
            proposed_fare=proposed_fare,
            agreed_fare=agreed_fare,
        )

    def test_customer_dashboard_displays_status_counts(self):
        for status in (
            TransportRequest.Status.PENDING,
            TransportRequest.Status.PENDING,
            TransportRequest.Status.ACCEPTED,
            TransportRequest.Status.CONFIRMED,
            TransportRequest.Status.COMPLETED,
            TransportRequest.Status.CANCELLED,
        ):
            self.create_ride(status=status)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        counts = response.context["customer_dashboard_counts"]
        self.assertEqual(counts["total"], 6)
        self.assertEqual(counts["pending"], 2)
        self.assertEqual(counts["accepted"], 1)
        self.assertEqual(counts["confirmed"], 1)
        self.assertEqual(counts["completed"], 1)
        self.assertEqual(counts["cancelled"], 1)

    def test_customer_dashboard_displays_ride_details_and_fares(self):
        self.create_ride(
            pickup="Soweto",
            destination="Sandton",
            proposed_fare=Decimal("180.00"),
        )
        self.create_ride(
            pickup="Tembisa",
            destination="Pretoria",
            status=TransportRequest.Status.CONFIRMED,
            proposed_fare=Decimal("250.00"),
            agreed_fare=Decimal("230.00"),
        )

        response = self.client.get(self.url)

        self.assertContains(response, "Soweto")
        self.assertContains(response, "Sandton")
        self.assertContains(response, "Proposed fare: R180.00")
        self.assertContains(response, "Agreed fare: R230.00")
        self.assertContains(response, "Confirmed")

    def test_customer_dashboard_shows_only_own_rides(self):
        other_customer = User.objects.create_user(
            username="another_dashboard_customer",
            password="Customer!Secure2026",
        )
        UserProfile.objects.create(
            user=other_customer,
            role=UserProfile.Role.CUSTOMER,
        )

        self.create_ride(
            pickup="MY_PRIVATE_PICKUP",
            destination="My destination",
        )
        self.create_ride(
            customer=other_customer,
            pickup="OTHER_CUSTOMER_PRIVATE_PICKUP",
            destination="Other destination",
        )

        response = self.client.get(self.url)

        self.assertContains(response, "MY_PRIVATE_PICKUP")
        self.assertNotContains(response, "OTHER_CUSTOMER_PRIVATE_PICKUP")
        self.assertEqual(
            response.context["customer_dashboard_counts"]["total"],
            1,
        )

    def test_customer_dashboard_limits_recent_rides_to_three(self):
        for index in range(5):
            self.create_ride(
                pickup=f"Pickup {index}",
                destination=f"Destination {index}",
                days_ahead=index + 1,
            )

        response = self.client.get(self.url)

        recent_rides = response.context["customer_dashboard_recent_rides"]
        self.assertEqual(len(recent_rides), 3)

    def test_customer_dashboard_shows_empty_state(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No ride requests yet")
        self.assertContains(response, "Request your first ride")
        self.assertEqual(
            response.context["customer_dashboard_counts"]["total"],
            0,
        )
