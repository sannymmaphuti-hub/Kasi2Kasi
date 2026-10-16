from datetime import timedelta

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

