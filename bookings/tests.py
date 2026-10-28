from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from .models import TransportRequest


User = get_user_model()


class BookingTestBase(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="bookingcustomer",
            password="Customer!Secure2026",
            first_name="Test",
            last_name="Passenger",
        )
        UserProfile.objects.create(
            user=self.customer,
            role=UserProfile.Role.CUSTOMER,
        )

    def future_datetime_string(self):
        future_datetime = (
            timezone.localtime() + timedelta(days=2)
        ).replace(second=0, microsecond=0)

        return future_datetime.strftime("%Y-%m-%dT%H:%M")

    def valid_booking_data(self):
        return {
            "customer_name": "Test Passenger",
            "contact_number": "0712345678",
            "pickup_location": "Bochum",
            "destination": "Witten",
            "travel_datetime": self.future_datetime_string(),
            "passenger_count": 1,
            "additional_notes": "",
        }


class BookingPageTests(BookingTestBase):
    def test_homepage_loads(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your journey.")

    def test_ride_request_page_requires_login(self):
        response = self.client.get(reverse("request_ride"))

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('request_ride')}",
        )

    def test_signed_in_customer_can_open_ride_request_page(self):
        self.client.force_login(self.customer)

        response = self.client.get(reverse("request_ride"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Request your ride.")


class TransportRequestTests(BookingTestBase):
    def test_valid_ride_request_is_saved_for_customer(self):
        self.client.force_login(self.customer)

        response = self.client.post(
            reverse("request_ride"),
            self.valid_booking_data(),
        )

        self.assertRedirects(
            response,
            reverse("request_ride"),
        )

        self.assertEqual(TransportRequest.objects.count(), 1)

        booking = TransportRequest.objects.get()

        self.assertEqual(booking.customer, self.customer)
        self.assertEqual(booking.customer_name, "Test Passenger")
        self.assertEqual(booking.pickup_location, "Bochum")
        self.assertEqual(booking.destination, "Witten")
        self.assertEqual(booking.status, TransportRequest.Status.PENDING)

    def test_past_ride_request_is_rejected(self):
        self.client.force_login(self.customer)

        past_datetime = (
            timezone.localtime() - timedelta(days=1)
        ).replace(second=0, microsecond=0)

        data = self.valid_booking_data()
        data["travel_datetime"] = past_datetime.strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = self.client.post(
            reverse("request_ride"),
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TransportRequest.objects.count(), 0)
        self.assertContains(
            response,
            "Please choose a future date and time.",
        )



    def test_customer_cannot_assign_booking_to_another_account(self):
        other_customer = User.objects.create_user(
            username="ownershiptarget",
            password="Other!Secure2026",
        )

        self.client.force_login(self.customer)

        data = self.valid_booking_data()
        data["customer"] = str(other_customer.pk)

        response = self.client.post(
            reverse("request_ride"),
            data,
        )

        self.assertRedirects(
            response,
            reverse("request_ride"),
        )

        booking = TransportRequest.objects.get()

        self.assertEqual(booking.customer, self.customer)
        self.assertNotEqual(booking.customer, other_customer)
    def test_driver_cannot_submit_customer_booking(self):
        driver = User.objects.create_user(
            username="bookingdriver",
            password="Driver!Secure2026",
        )
        UserProfile.objects.create(
            user=driver,
            role=UserProfile.Role.DRIVER,
        )
        self.client.force_login(driver)

        response = self.client.post(
            reverse("request_ride"),
            self.valid_booking_data(),
        )

        self.assertRedirects(
            response,
            reverse("account_dashboard"),
        )
        self.assertEqual(TransportRequest.objects.count(), 0)


class CustomerRideHistoryTests(BookingTestBase):
    def test_customer_sees_only_own_rides(self):
        other_customer = User.objects.create_user(
            username="othercustomer",
            password="Other!Secure2026",
        )

        own_ride = TransportRequest.objects.create(
            customer=self.customer,
            **{
                **self.valid_booking_data(),
                "travel_datetime": timezone.localtime() + timedelta(days=2),
            },
        )

        other_ride = TransportRequest.objects.create(
            customer=other_customer,
            customer_name="Other Passenger",
            contact_number="0798765432",
            pickup_location="Polokwane",
            destination="Tzaneen",
            travel_datetime=timezone.localtime() + timedelta(days=3),
            passenger_count=1,
        )

        self.client.force_login(self.customer)

        response = self.client.get(reverse("my_rides"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_ride.pickup_location)
        self.assertNotContains(response, other_ride.pickup_location)

    def test_ride_history_requires_login(self):
        response = self.client.get(reverse("my_rides"))

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('my_rides')}",
        )

class CustomerRideCancellationTests(BookingTestBase):
    def create_ride(self, customer=None, status=None):
        data = self.valid_booking_data()
        data["travel_datetime"] = timezone.localtime() + timedelta(days=2)

        booking = TransportRequest.objects.create(
            customer=customer or self.customer,
            **data,
        )
        if status is not None:
            booking.status = status
            booking.save(update_fields=["status"])
        return booking

    def test_customer_can_cancel_own_pending_ride(self):
        booking = self.create_ride()
        self.client.force_login(self.customer)

        response = self.client.post(
            reverse("cancel_ride", args=[booking.pk])
        )

        self.assertRedirects(response, reverse("my_rides"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, TransportRequest.Status.CANCELLED)

    def test_cancelling_ride_stops_and_clears_live_location(self):
        from bookings.models import DriverLiveLocation

        booking = self.create_ride()

        driver = User.objects.create_user(
            username="gpscancellationdriver",
            password="Driver!Secure2026",
        )
        UserProfile.objects.create(
            user=driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
        )

        location = DriverLiveLocation.objects.create(
            ride=booking,
            driver=driver,
            latitude=-23.900000,
            longitude=29.400000,
            is_sharing=True,
        )

        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("cancel_ride", args=[booking.pk])
        )

        self.assertRedirects(response, reverse("my_rides"))

        booking.refresh_from_db()
        location.refresh_from_db()

        self.assertEqual(booking.status, TransportRequest.Status.CANCELLED)
        self.assertFalse(location.is_sharing)
        self.assertIsNone(location.latitude)
        self.assertIsNone(location.longitude)

    def test_customer_cannot_cancel_another_customers_ride(self):
        other_customer = User.objects.create_user(
            username="cancellationowner",
            password="Other!Secure2026",
        )
        booking = self.create_ride(customer=other_customer)
        self.client.force_login(self.customer)

        response = self.client.post(
            reverse("cancel_ride", args=[booking.pk])
        )

        self.assertEqual(response.status_code, 404)
        booking.refresh_from_db()
        self.assertEqual(booking.status, TransportRequest.Status.PENDING)

    def test_non_pending_ride_cannot_be_cancelled(self):
        booking = self.create_ride(status=TransportRequest.Status.ACCEPTED)
        self.client.force_login(self.customer)

        response = self.client.post(
            reverse("cancel_ride", args=[booking.pk])
        )

        self.assertRedirects(response, reverse("my_rides"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, TransportRequest.Status.ACCEPTED)

    def test_driver_cannot_cancel_customer_ride(self):
        driver = User.objects.create_user(
            username="cancellationdriver",
            password="Driver!Secure2026",
        )
        UserProfile.objects.create(
            user=driver,
            role=UserProfile.Role.DRIVER,
        )
        booking = self.create_ride()
        self.client.force_login(driver)

        response = self.client.post(
            reverse("cancel_ride", args=[booking.pk])
        )

        self.assertRedirects(response, reverse("account_dashboard"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, TransportRequest.Status.PENDING)

    def test_get_request_cannot_cancel_ride(self):
        booking = self.create_ride()
        self.client.force_login(self.customer)

        response = self.client.get(
            reverse("cancel_ride", args=[booking.pk])
        )

        self.assertEqual(response.status_code, 405)
        booking.refresh_from_db()
        self.assertEqual(booking.status, TransportRequest.Status.PENDING)

    def test_cancelled_ride_does_not_show_cancel_button(self):
        booking = self.create_ride(status=TransportRequest.Status.CANCELLED)
        self.client.force_login(self.customer)

        response = self.client.get(reverse("my_rides"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Cancel ride request")

class CustomerRideFareConfirmationTests(BookingTestBase):
    def create_accepted_ride(self, customer=None, proposed_fare="150.00"):
        data = self.valid_booking_data()
        data["travel_datetime"] = timezone.localtime() + timedelta(days=2)
        return TransportRequest.objects.create(
            customer=customer or self.customer,
            proposed_fare=proposed_fare,
            status=TransportRequest.Status.ACCEPTED,
            **data,
        )

    def test_customer_can_confirm_own_accepted_ride_fare(self):
        booking = self.create_accepted_ride()
        self.client.force_login(self.customer)
        response = self.client.post(reverse("confirm_ride_fare", args=[booking.pk]))
        self.assertRedirects(response, reverse("my_rides"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, TransportRequest.Status.CONFIRMED)
        self.assertEqual(booking.agreed_fare, booking.proposed_fare)

    def test_confirming_proposed_fare_preserves_original_estimate(self):
        booking = self.create_accepted_ride(proposed_fare="150.00")
        booking.estimated_fare = Decimal("75.00")
        booking.save(update_fields=["estimated_fare"])

        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("confirm_ride_fare", args=[booking.pk])
        )

        self.assertRedirects(response, reverse("my_rides"))
        booking.refresh_from_db()
        self.assertEqual(booking.estimated_fare, Decimal("75.00"))
        self.assertEqual(booking.proposed_fare, Decimal("150.00"))
        self.assertEqual(booking.agreed_fare, Decimal("150.00"))
        self.assertEqual(booking.status, TransportRequest.Status.CONFIRMED)
    def test_customer_cannot_confirm_another_customers_ride(self):
        other_customer = User.objects.create_user(
            username="fareconfirmationowner",
            password="Other!Secure2026",
        )
        booking = self.create_accepted_ride(customer=other_customer)
        self.client.force_login(self.customer)
        response = self.client.post(reverse("confirm_ride_fare", args=[booking.pk]))
        self.assertEqual(response.status_code, 404)
        booking.refresh_from_db()
        self.assertEqual(booking.status, TransportRequest.Status.ACCEPTED)
        self.assertIsNone(booking.agreed_fare)

    def test_driver_cannot_confirm_customer_fare(self):
        driver = User.objects.create_user(
            username="fareconfirmationdriver",
            password="Driver!Secure2026",
        )
        UserProfile.objects.create(
            user=driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.APPROVED,
        )
        booking = self.create_accepted_ride()
        self.client.force_login(driver)
        response = self.client.post(reverse("confirm_ride_fare", args=[booking.pk]))
        self.assertRedirects(response, reverse("account_dashboard"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, TransportRequest.Status.ACCEPTED)
        self.assertIsNone(booking.agreed_fare)

    def test_ride_without_proposed_fare_cannot_be_confirmed(self):
        booking = self.create_accepted_ride(proposed_fare=None)
        self.client.force_login(self.customer)
        response = self.client.post(reverse("confirm_ride_fare", args=[booking.pk]))
        self.assertRedirects(response, reverse("my_rides"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, TransportRequest.Status.ACCEPTED)
        self.assertIsNone(booking.agreed_fare)

    def test_pending_ride_cannot_be_confirmed(self):
        data = self.valid_booking_data()
        data["travel_datetime"] = timezone.localtime() + timedelta(days=2)
        booking = TransportRequest.objects.create(
            customer=self.customer,
            proposed_fare="150.00",
            **data,
        )
        self.client.force_login(self.customer)
        response = self.client.post(reverse("confirm_ride_fare", args=[booking.pk]))
        self.assertRedirects(response, reverse("my_rides"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, TransportRequest.Status.PENDING)
        self.assertIsNone(booking.agreed_fare)

    def test_get_request_cannot_confirm_fare(self):
        booking = self.create_accepted_ride()
        self.client.force_login(self.customer)
        response = self.client.get(reverse("confirm_ride_fare", args=[booking.pk]))
        self.assertEqual(response.status_code, 405)
        booking.refresh_from_db()
        self.assertEqual(booking.status, TransportRequest.Status.ACCEPTED)
        self.assertIsNone(booking.agreed_fare)

    def test_accepted_ride_shows_confirmation_button(self):
        self.create_accepted_ride()
        self.client.force_login(self.customer)
        response = self.client.get(reverse("my_rides"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm fare and ride")
