from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from bookings.models import TransportRequest


User = get_user_model()


class DriverRideNavigationTests(TestCase):
    def setUp(self):
        self.driver = User.objects.create_user(
            username="navigation_driver",
            password="Test!Secure2026",
        )
        UserProfile.objects.create(
            user=self.driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
        )
        self.other_driver = User.objects.create_user(
            username="other_navigation_driver",
            password="Test!Secure2026",
        )
        UserProfile.objects.create(
            user=self.other_driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
        )
        self.ride = TransportRequest.objects.create(
            assigned_driver=self.driver,
            customer_name="Navigation Passenger",
            contact_number="0712345678",
            pickup_location="Pickup Point",
            destination="Destination Point",
            pickup_latitude=Decimal("-25.749041"),
            pickup_longitude=Decimal("28.217831"),
            destination_latitude=Decimal("-25.746526"),
            destination_longitude=Decimal("28.212687"),
            travel_datetime=timezone.now() + timedelta(days=1),
            passenger_count=1,
        )
        self.url = reverse(
            "driver_ride_navigation",
            args=[self.ride.pk],
        )

    def test_assigned_driver_can_open_navigation(self):
        self.client.force_login(self.driver)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pickup Point")
        self.assertContains(response, "Destination Point")
        self.assertContains(response, "Navigate with Google Maps")
        self.assertContains(response, "25.749041")
        self.assertContains(response, "28.212687")

    def test_other_driver_cannot_view_ride_navigation(self):
        self.client.force_login(self.other_driver)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_google_maps_link_is_not_rendered_without_both_endpoints(self):
        self.ride.destination_latitude = None
        self.ride.destination_longitude = None
        self.ride.save(update_fields=[
            "destination_latitude",
            "destination_longitude",
        ])
        self.client.force_login(self.driver)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Navigate with Google Maps")


    def test_assigned_driver_can_confirm_pickup(self):
        self.ride.status = TransportRequest.Status.CONFIRMED
        self.ride.save(update_fields=["status"])
        self.client.force_login(self.driver)

        response = self.client.post(
            reverse("confirm_assigned_ride_pickup", args=[self.ride.pk])
        )

        self.assertRedirects(response, self.url)
        self.ride.refresh_from_db()
        self.assertIsNotNone(self.ride.pickup_confirmed_at)

    def test_other_driver_cannot_confirm_pickup(self):
        self.ride.status = TransportRequest.Status.CONFIRMED
        self.ride.save(update_fields=["status"])
        self.client.force_login(self.other_driver)

        response = self.client.post(
            reverse("confirm_assigned_ride_pickup", args=[self.ride.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.pickup_confirmed_at)

    def test_pickup_confirmation_rejects_get_requests(self):
        self.client.force_login(self.driver)

        response = self.client.get(
            reverse("confirm_assigned_ride_pickup", args=[self.ride.pk])
        )

        self.assertEqual(response.status_code, 405)

    def test_unconfirmed_ride_cannot_confirm_pickup(self):
        self.client.force_login(self.driver)

        response = self.client.post(
            reverse("confirm_assigned_ride_pickup", args=[self.ride.pk])
        )

        self.assertRedirects(response, self.url)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.pickup_confirmed_at)

    def test_navigation_shows_pickup_confirmation_until_confirmed(self):
        from django.utils import timezone

        self.ride.status = TransportRequest.Status.CONFIRMED
        self.ride.save(update_fields=["status"])
        self.client.force_login(self.driver)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "I have picked up the passenger")
        self.assertNotContains(
            response,
            "Pickup confirmed. Destination navigation is enabled.",
        )

        self.ride.pickup_confirmed_at = timezone.now()
        self.ride.save(update_fields=["pickup_confirmed_at"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Pickup confirmed. Destination navigation is enabled.",
        )
        self.assertNotContains(response, "I have picked up the passenger")
