from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from bookings.models import TransportRequest


User = get_user_model()


class DispatchOverviewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="dispatch_staff",
            password="TestPassword!234",
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username="dispatch_customer",
            password="TestPassword!234",
        )
        UserProfile.objects.create(
            user=self.customer,
            role=UserProfile.Role.CUSTOMER,
        )

        self.driver = User.objects.create_user(
            username="online_dispatch_driver",
            password="TestPassword!234",
        )
        UserProfile.objects.create(
            user=self.driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
            is_available=True,
        )

        self.ride = TransportRequest.objects.create(
            customer=self.customer,
            customer_name="Dispatch Customer",
            contact_number="0712345678",
            pickup_location="Pickup A",
            destination="Destination B",
            travel_datetime=timezone.now() + timedelta(days=1),
            passenger_count=1,
            status=TransportRequest.Status.PENDING,
        )

        self.url = reverse("dispatch_overview")

    def test_anonymous_user_is_redirected_to_staff_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_non_staff_user_is_denied(self):
        self.client.force_login(self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_staff_can_view_dispatch_dashboard(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "bookings/dispatch_overview.html")
        self.assertContains(response, "Kasi2Kasi Dispatch")
        self.assertContains(response, "Dispatch Customer")
        self.assertContains(response, "Unassigned active")

    def test_dashboard_counts_and_online_drivers(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.context["ride_counts"]["total"], 1)
        self.assertEqual(response.context["ride_counts"]["pending"], 1)
        self.assertEqual(response.context["ride_counts"]["unassigned"], 1)
        self.assertContains(response, "online_dispatch_driver")

    def test_staff_can_filter_by_status(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url, {"status": "CANCELLED"})

        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(response.context["rides"], [])

    def test_invalid_status_filter_does_not_break_dashboard(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url, {"status": "NOT_A_STATUS"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_status"], "")
        self.assertEqual(len(response.context["rides"]), 1)

    def test_staff_can_assign_pending_ride_to_online_approved_driver(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("assign_dispatch_ride", args=[self.ride.pk]),
            {"driver_id": str(self.driver.pk)},
        )

        self.assertRedirects(response, self.url)
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.assigned_driver_id, self.driver.pk)
        self.assertEqual(self.ride.status, TransportRequest.Status.PENDING)

    def test_non_staff_cannot_assign_ride(self):
        self.client.force_login(self.customer)

        response = self.client.post(
            reverse("assign_dispatch_ride", args=[self.ride.pk]),
            {"driver_id": str(self.driver.pk)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.assigned_driver_id)

    def test_assignment_endpoint_rejects_get(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("assign_dispatch_ride", args=[self.ride.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.assigned_driver_id)

    def test_offline_driver_cannot_be_assigned(self):
        self.client.force_login(self.staff)
        self.driver.profile.is_available = False
        self.driver.profile.save(update_fields=["is_available"])

        response = self.client.post(
            reverse("assign_dispatch_ride", args=[self.ride.pk]),
            {"driver_id": str(self.driver.pk)},
        )

        self.assertRedirects(response, self.url)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.assigned_driver_id)

    def test_unapproved_driver_cannot_be_assigned(self):
        self.client.force_login(self.staff)

        unapproved_driver = User.objects.create_user(
            username="unapproved_dispatch_driver",
            password="TestPassword!234",
        )
        UserProfile.objects.create(
            user=unapproved_driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.PENDING,
            is_available=True,
        )

        response = self.client.post(
            reverse("assign_dispatch_ride", args=[self.ride.pk]),
            {"driver_id": str(unapproved_driver.pk)},
        )

        self.assertRedirects(response, self.url)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.assigned_driver_id)

    def test_customer_account_cannot_be_assigned_as_driver(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("assign_dispatch_ride", args=[self.ride.pk]),
            {"driver_id": str(self.customer.pk)},
        )

        self.assertRedirects(response, self.url)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.assigned_driver_id)

    def test_invalid_driver_id_is_rejected(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("assign_dispatch_ride", args=[self.ride.pk]),
            {"driver_id": "not-a-driver"},
        )

        self.assertRedirects(response, self.url)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.assigned_driver_id)

    def test_nonexistent_driver_id_is_rejected(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("assign_dispatch_ride", args=[self.ride.pk]),
            {"driver_id": "999999"},
        )

        self.assertRedirects(response, self.url)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.assigned_driver_id)

    def test_driver_with_same_departure_time_conflict_is_rejected(self):
        self.client.force_login(self.staff)

        TransportRequest.objects.create(
            assigned_driver=self.driver,
            customer_name="Existing Passenger",
            contact_number="0712345678",
            pickup_location="Soweto",
            destination="Johannesburg",
            travel_datetime=self.ride.travel_datetime,
            passenger_count=1,
            proposed_fare="100.00",
            status=TransportRequest.Status.CONFIRMED,
            agreed_fare="100.00",
        )

        response = self.client.post(
            reverse("assign_dispatch_ride", args=[self.ride.pk]),
            {"driver_id": str(self.driver.pk)},
        )

        self.assertRedirects(response, self.url)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.assigned_driver_id)

    def test_already_assigned_ride_cannot_be_reassigned(self):
        self.client.force_login(self.staff)

        another_driver = User.objects.create_user(
            username="another_dispatch_driver",
            password="TestPassword!234",
        )
        UserProfile.objects.create(
            user=another_driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
            is_available=True,
        )

        self.ride.assigned_driver = another_driver
        self.ride.save(update_fields=["assigned_driver"])

        response = self.client.post(
            reverse("assign_dispatch_ride", args=[self.ride.pk]),
            {"driver_id": str(self.driver.pk)},
        )

        self.assertRedirects(response, self.url)
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.assigned_driver_id, another_driver.pk)

    def test_non_pending_ride_cannot_be_assigned(self):
        self.client.force_login(self.staff)
        self.ride.status = TransportRequest.Status.CANCELLED
        self.ride.save(update_fields=["status"])

        response = self.client.post(
            reverse("assign_dispatch_ride", args=[self.ride.pk]),
            {"driver_id": str(self.driver.pk)},
        )

        self.assertRedirects(response, self.url)
        self.ride.refresh_from_db()
        self.assertIsNone(self.ride.assigned_driver_id)
