from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from bookings.models import TransportRequest


User = get_user_model()


class DriverDashboardOverviewTests(TestCase):
    def setUp(self):
        self.driver = User.objects.create_user(
            username="overview_driver",
            password="TestPassword!234",
        )
        self.driver_profile = UserProfile.objects.create(
            user=self.driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
            is_available=True,
        )

        self.customer = User.objects.create_user(
            username="overview_customer",
            password="TestPassword!234",
        )
        UserProfile.objects.create(
            user=self.customer,
            role=UserProfile.Role.CUSTOMER,
        )

        self.url = reverse("account_dashboard")

    def create_ride(self, status, days_from_now=2, suffix=""):
        return TransportRequest.objects.create(
            customer=self.customer,
            assigned_driver=self.driver,
            customer_name="Dashboard Customer",
            contact_number="0712345678",
            pickup_location=f"Pickup {suffix}",
            destination=f"Destination {suffix}",
            travel_datetime=timezone.now() + timedelta(days=days_from_now),
            passenger_count=1,
            status=status,
        )

    def test_approved_driver_sees_ride_summary_counts(self):
        self.create_ride(TransportRequest.Status.PENDING, suffix="pending")
        self.create_ride(TransportRequest.Status.ACCEPTED, suffix="accepted")
        self.create_ride(TransportRequest.Status.CONFIRMED, suffix="confirmed")
        self.create_ride(TransportRequest.Status.COMPLETED, suffix="completed")

        self.client.force_login(self.driver)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_counts"]["assigned"], 4)
        self.assertEqual(response.context["dashboard_counts"]["pending"], 1)
        self.assertEqual(response.context["dashboard_counts"]["accepted"], 1)
        self.assertEqual(response.context["dashboard_counts"]["confirmed"], 1)
        self.assertEqual(response.context["dashboard_counts"]["completed"], 1)

    def test_upcoming_journeys_are_shown_in_travel_time_order(self):
        later = self.create_ride(
            TransportRequest.Status.CONFIRMED,
            days_from_now=3,
            suffix="later",
        )
        earlier = self.create_ride(
            TransportRequest.Status.PENDING,
            days_from_now=1,
            suffix="earlier",
        )
        self.create_ride(
            TransportRequest.Status.CANCELLED,
            days_from_now=1,
            suffix="cancelled",
        )

        self.client.force_login(self.driver)
        response = self.client.get(self.url)

        upcoming = list(response.context["dashboard_upcoming_rides"])
        self.assertEqual([ride.pk for ride in upcoming], [earlier.pk, later.pk])
        self.assertContains(response, "Next upcoming journeys")
        self.assertContains(response, "Pickup earlier")
        self.assertNotContains(response, "Pickup cancelled")

    def test_dashboard_limits_upcoming_journeys_to_three(self):
        for index in range(5):
            self.create_ride(
                TransportRequest.Status.CONFIRMED,
                days_from_now=index + 1,
                suffix=str(index),
            )

        self.client.force_login(self.driver)
        response = self.client.get(self.url)

        self.assertEqual(len(response.context["dashboard_upcoming_rides"]), 3)

    def test_unapproved_driver_does_not_receive_ride_summary(self):
        self.driver_profile.driver_status = UserProfile.DriverStatus.PENDING
        self.driver_profile.save(update_fields=["driver_status"])

        self.client.force_login(self.driver)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("dashboard_counts", response.context)
        self.assertNotContains(response, "Your ride overview")
        self.assertContains(response, "pending approval")

    def test_dashboard_keeps_existing_availability_controls(self):
        self.client.force_login(self.driver)
        response = self.client.get(self.url)

        self.assertContains(response, "Go offline")
        self.assertContains(response, "View my assigned rides")
