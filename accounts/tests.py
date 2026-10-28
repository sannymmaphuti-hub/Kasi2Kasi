from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import DriverVehicle, UserProfile


User = get_user_model()


class AccountRegistrationTests(TestCase):
    def registration_data(self, username, email):
        return {
            "username": username,
            "first_name": "Test",
            "last_name": "User",
            "email": email,
            "password1": "KasiTest!2026Secure",
            "password2": "KasiTest!2026Secure",
        }

    def driver_registration_data(self, username, email, registration_number="ABC123"):
        data = self.registration_data(username, email)
        data.update({
            "vehicle_type": "SEDAN",
            "make": "Toyota",
            "model": "Corolla",
            "year": "2018",
            "registration_number": registration_number,
            "passenger_capacity": "4",
        })
        return data

    def test_customer_registration_creates_customer_profile(self):
        response = self.client.post(
            reverse("customer_signup"),
            self.registration_data(
                "testcustomer",
                "customer@example.com",
            ),
        )

        self.assertRedirects(
            response,
            reverse("account_dashboard"),
        )

        user = User.objects.get(username="testcustomer")
        self.assertEqual(user.profile.role, UserProfile.Role.CUSTOMER)
        self.assertEqual(
            user.profile.driver_status,
            UserProfile.DriverStatus.NOT_APPLICABLE,
        )

    def test_driver_registration_creates_pending_driver_profile(self):
        response = self.client.post(
            reverse("driver_signup"),
            self.driver_registration_data(
                "testdriver",
                "driver@example.com",
            ),
        )

        self.assertRedirects(
            response,
            reverse("account_dashboard"),
        )

        user = User.objects.get(username="testdriver")
        self.assertEqual(user.profile.role, UserProfile.Role.DRIVER)
        self.assertEqual(
            user.profile.driver_status,
            UserProfile.DriverStatus.PENDING,
        )

        vehicle = DriverVehicle.objects.get(driver=user)
        self.assertEqual(vehicle.vehicle_type, DriverVehicle.VehicleType.SEDAN)
        self.assertEqual(vehicle.make, "Toyota")
        self.assertEqual(vehicle.model, "Corolla")
        self.assertEqual(vehicle.registration_number, "ABC123")
        self.assertEqual(vehicle.passenger_capacity, 4)
        self.assertTrue(vehicle.is_active)
        self.assertFalse(vehicle.verified)

    def test_duplicate_vehicle_registration_is_rejected(self):
        existing_driver = User.objects.create_user(
            username="existingdriver",
            email="existingdriver@example.com",
            password="Existing!Secure2026",
        )
        UserProfile.objects.create(
            user=existing_driver,
            role=UserProfile.Role.DRIVER,
            driver_status=UserProfile.DriverStatus.PENDING,
        )
        DriverVehicle.objects.create(
            driver=existing_driver,
            vehicle_type=DriverVehicle.VehicleType.SEDAN,
            make="Toyota",
            model="Corolla",
            registration_number="ABC123",
            passenger_capacity=4,
        )

        response = self.client.post(
            reverse("driver_signup"),
            self.driver_registration_data(
                "duplicatevehicle",
                "duplicatevehicle@example.com",
                registration_number=" abc123 ",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="duplicatevehicle").exists())
        self.assertEqual(
            DriverVehicle.objects.filter(registration_number__iexact="ABC123").count(),
            1,
        )

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(
            username="existinguser",
            email="existing@example.com",
            password="Existing!Secure2026",
        )

        response = self.client.post(
            reverse("customer_signup"),
            self.registration_data(
                "anotheruser",
                "EXISTING@example.com",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(username="anotheruser").exists()
        )


class AccountAccessTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer",
            password="Customer!Secure2026",
        )
        UserProfile.objects.create(
            user=self.customer,
            role=UserProfile.Role.CUSTOMER,
        )

        self.driver = User.objects.create_user(
            username="driver",
            password="Driver!Secure2026",
        )
        UserProfile.objects.create(
            user=self.driver,
            role=UserProfile.Role.DRIVER,
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("account_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("account_login"),
            response.url,
        )

    def test_customer_is_sent_to_customer_dashboard(self):
        self.client.force_login(self.customer)

        response = self.client.get(reverse("account_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "accounts/customer_dashboard.html",
        )

    def test_driver_is_sent_to_driver_dashboard(self):
        self.client.force_login(self.driver)

        response = self.client.get(reverse("account_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "accounts/driver_dashboard.html",
        )
        self.assertContains(response, "pending approval")

    def test_login_and_post_logout(self):
        response = self.client.post(
            reverse("account_login"),
            {
                "username": "customer",
                "password": "Customer!Secure2026",
            },
        )

        self.assertRedirects(
            response,
            reverse("account_dashboard"),
        )

        response = self.client.post(reverse("account_logout"))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)



    def test_driver_can_toggle_own_vehicle_without_changing_verification(self):
        vehicle = self.create_vehicle(is_active=False, verified=True)
        self.client.force_login(self.driver)
        url = reverse("toggle_vehicle_active", kwargs={"vehicle_id": vehicle.pk})

        response = self.client.post(url)
        self.assertRedirects(response, reverse("driver_vehicle_management"))

        vehicle.refresh_from_db()
        self.assertTrue(vehicle.is_active)
        self.assertTrue(vehicle.verified)

        response = self.client.post(url)
        self.assertRedirects(response, reverse("driver_vehicle_management"))

        vehicle.refresh_from_db()
        self.assertFalse(vehicle.is_active)
        self.assertTrue(vehicle.verified)

    def test_driver_cannot_toggle_another_drivers_vehicle(self):
        other_driver = User.objects.create_user(
            username="otherdriver",
            password="OtherDriver!Secure2026",
        )
        UserProfile.objects.create(
            user=other_driver,
            role=UserProfile.Role.DRIVER,
        )
        vehicle = self.create_vehicle(
            driver=other_driver,
            registration_number="OTHER123",
            is_active=True,
            verified=True,
        )
        self.client.force_login(self.driver)
        url = reverse("toggle_vehicle_active", kwargs={"vehicle_id": vehicle.pk})

        response = self.client.post(url)
        self.assertRedirects(response, reverse("driver_vehicle_management"))

        vehicle.refresh_from_db()
        self.assertTrue(vehicle.is_active)
        self.assertTrue(vehicle.verified)

    def test_customer_cannot_toggle_vehicle_activation(self):
        vehicle = self.create_vehicle(is_active=True, verified=True)
        self.client.force_login(self.customer)
        url = reverse("toggle_vehicle_active", kwargs={"vehicle_id": vehicle.pk})

        response = self.client.post(url)
        self.assertRedirects(response, reverse("account_dashboard"))

        vehicle.refresh_from_db()
        self.assertTrue(vehicle.is_active)
        self.assertTrue(vehicle.verified)

    def test_vehicle_activation_rejects_get(self):
        vehicle = self.create_vehicle(is_active=True, verified=True)
        self.client.force_login(self.driver)
        url = reverse("toggle_vehicle_active", kwargs={"vehicle_id": vehicle.pk})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

        vehicle.refresh_from_db()
        self.assertTrue(vehicle.is_active)
        self.assertTrue(vehicle.verified)

    def create_vehicle(self, driver=None, **overrides):
        driver = driver or self.driver
        values = {
            "vehicle_type": "SEDAN",
            "make": "Toyota",
            "model": "Corolla",
            "year": 2018,
            "registration_number": "ABC123",
            "passenger_capacity": 4,
            "is_active": True,
            "verified": False,
        }
        values.update(overrides)
        return DriverVehicle.objects.create(driver=driver, **values)

    def vehicle_form_data(self, vehicle, **overrides):
        values = {
            "vehicle_type": vehicle.vehicle_type,
            "make": vehicle.make,
            "model": vehicle.model,
            "year": vehicle.year,
            "registration_number": vehicle.registration_number,
            "passenger_capacity": vehicle.passenger_capacity,
        }
        values.update(overrides)
        return values

    def test_customer_cannot_access_vehicle_management(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("driver_vehicle_management"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("account_dashboard"))

    def test_vehicle_list_rejects_post(self):
        self.client.force_login(self.driver)
        response = self.client.post(reverse("driver_vehicle_management"))
        self.assertEqual(response.status_code, 405)

    def test_driver_cannot_edit_another_drivers_vehicle(self):
        other_driver = User.objects.create_user(
            username="otherdriver",
            password="OtherDriver!Secure2026",
        )
        UserProfile.objects.create(user=other_driver, role=UserProfile.Role.DRIVER)
        vehicle = self.create_vehicle(driver=other_driver, registration_number="XYZ789")
        self.client.force_login(self.driver)
        response = self.client.get(reverse("driver_vehicle_edit", kwargs={"vehicle_id": vehicle.pk}))
        self.assertRedirects(response, reverse("driver_vehicle_management"))
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.registration_number, "XYZ789")

    def test_vehicle_edit_resets_verification_when_details_change(self):
        vehicle = self.create_vehicle(verified=True)
        self.client.force_login(self.driver)
        response = self.client.post(reverse("driver_vehicle_edit", kwargs={"vehicle_id": vehicle.pk}), self.vehicle_form_data(vehicle, model="Yaris"))
        self.assertRedirects(response, reverse("driver_vehicle_management"))
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.model, "Yaris")
        self.assertFalse(vehicle.verified)

    def test_vehicle_edit_preserves_verification_when_details_unchanged(self):
        vehicle = self.create_vehicle(verified=True)
        self.client.force_login(self.driver)
        response = self.client.post(reverse("driver_vehicle_edit", kwargs={"vehicle_id": vehicle.pk}), self.vehicle_form_data(vehicle))
        self.assertRedirects(response, reverse("driver_vehicle_management"))
        vehicle.refresh_from_db()
        self.assertTrue(vehicle.verified)

    def test_vehicle_edit_rejects_duplicate_registration(self):
        vehicle = self.create_vehicle()
        self.create_vehicle(driver=self.customer, registration_number="XYZ789")
        self.client.force_login(self.driver)
        response = self.client.post(reverse("driver_vehicle_edit", kwargs={"vehicle_id": vehicle.pk}), self.vehicle_form_data(vehicle, registration_number=" xyz789 "))
        self.assertEqual(response.status_code, 200)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.registration_number, "ABC123")


class DriverApprovalAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="siteadmin",
            email="siteadmin@example.com",
            password="Admin!Secure2026",
        )

        self.driver = User.objects.create_user(
            username="approvaldriver",
            password="Driver!Secure2026",
        )
        self.driver_profile = UserProfile.objects.create(
            user=self.driver,
            role=UserProfile.Role.DRIVER,
        )

        self.customer = User.objects.create_user(
            username="approvalcustomer",
            password="Customer!Secure2026",
        )
        self.customer_profile = UserProfile.objects.create(
            user=self.customer,
            role=UserProfile.Role.CUSTOMER,
        )

        self.action_url = reverse(
            "admin:accounts_userprofile_changelist"
        )

    def run_admin_action(self, action, profile):
        self.client.force_login(self.admin_user)
        return self.client.post(
            self.action_url,
            {
                "action": action,
                "_selected_action": [str(profile.pk)],
            },
        )

    def test_admin_can_approve_driver(self):
        response = self.run_admin_action(
            "approve_drivers",
            self.driver_profile,
        )

        self.assertEqual(response.status_code, 302)
        self.driver_profile.refresh_from_db()
        self.assertEqual(
            self.driver_profile.driver_status,
            UserProfile.DriverStatus.APPROVED,
        )

    def test_admin_can_reject_driver(self):
        self.run_admin_action("reject_drivers", self.driver_profile)

        self.driver_profile.refresh_from_db()
        self.assertEqual(
            self.driver_profile.driver_status,
            UserProfile.DriverStatus.REJECTED,
        )

    def test_admin_can_suspend_driver(self):
        self.run_admin_action("suspend_drivers", self.driver_profile)

        self.driver_profile.refresh_from_db()
        self.assertEqual(
            self.driver_profile.driver_status,
            UserProfile.DriverStatus.SUSPENDED,
        )

    def test_driver_actions_do_not_change_customer_profiles(self):
        self.run_admin_action(
            "suspend_drivers",
            self.customer_profile,
        )

        self.customer_profile.refresh_from_db()
        self.assertEqual(
            self.customer_profile.driver_status,
            UserProfile.DriverStatus.NOT_APPLICABLE,
        )

    def test_all_driver_status_actions_reset_availability(self):
        actions = (
            ("approve_drivers", UserProfile.DriverStatus.APPROVED),
            ("reject_drivers", UserProfile.DriverStatus.REJECTED),
            ("suspend_drivers", UserProfile.DriverStatus.SUSPENDED),
        )

        for action, expected_status in actions:
            with self.subTest(action=action):
                self.driver_profile.driver_status = (
                    UserProfile.DriverStatus.APPROVED
                )
                self.driver_profile.is_available = True
                self.driver_profile.save(
                    update_fields=["driver_status", "is_available"]
                )

                self.run_admin_action(action, self.driver_profile)

                self.driver_profile.refresh_from_db()
                self.assertEqual(
                    self.driver_profile.driver_status,
                    expected_status,
                )
                self.assertFalse(self.driver_profile.is_available)

    def test_suspending_driver_preserves_existing_ride_assignment(self):
        ride = TransportRequest.objects.create(
            assigned_driver=self.driver,
            customer_name="Existing Passenger",
            contact_number="0712345678",
            pickup_location="Soweto",
            destination="Johannesburg",
            travel_datetime=timezone.now() + timedelta(days=1),
            passenger_count=1,
        )

        self.driver_profile.driver_status = (
            UserProfile.DriverStatus.APPROVED
        )
        self.driver_profile.is_available = True
        self.driver_profile.save(
            update_fields=["driver_status", "is_available"]
        )

        self.run_admin_action("suspend_drivers", self.driver_profile)

        self.driver_profile.refresh_from_db()
        ride.refresh_from_db()

        self.assertEqual(
            self.driver_profile.driver_status,
            UserProfile.DriverStatus.SUSPENDED,
        )
        self.assertFalse(self.driver_profile.is_available)
        self.assertEqual(ride.assigned_driver_id, self.driver.pk)

    def test_non_admin_cannot_access_admin_controls(self):
        self.client.force_login(self.customer)

        response = self.client.post(
            self.action_url,
            {
                "action": "approve_drivers",
                "_selected_action": [str(self.driver_profile.pk)],
            },
        )

        self.assertIn(response.status_code, (302, 403))
        self.driver_profile.refresh_from_db()
        self.assertEqual(
            self.driver_profile.driver_status,
            UserProfile.DriverStatus.PENDING,
        )


from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile


class ProfilePictureTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="picturecustomer",
            password="Customer!Secure2026",
        )
        self.profile = UserProfile.objects.create(
            user=self.customer,
            role=UserProfile.Role.CUSTOMER,
        )

        self.driver = User.objects.create_user(
            username="picturedriver",
            password="Driver!Secure2026",
        )
        self.driver_profile = UserProfile.objects.create(
            user=self.driver,
            role=UserProfile.Role.DRIVER,
        )

    def make_image(
        self,
        name="profile.png",
        image_format="PNG",
        size=(16, 16),
    ):
        buffer = BytesIO()
        Image.new("RGB", size, color="green").save(
            buffer,
            format=image_format,
        )
        return SimpleUploadedFile(
            name,
            buffer.getvalue(),
            content_type="image/png",
        )
    def test_customer_can_open_profile_settings(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("profile_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "accounts/profile_settings.html",
        )

    def test_customer_can_upload_own_profile_picture(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("profile_settings"),
            {"profile_picture": self.make_image()},
        )

        self.assertRedirects(response, reverse("profile_settings"))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.profile_picture.name.startswith(
            "profile_pictures/"
        ))

    def test_driver_can_upload_own_profile_picture(self):
        self.client.force_login(self.driver)
        response = self.client.post(
            reverse("profile_settings"),
            {"profile_picture": self.make_image("driver.png")},
        )

        self.assertRedirects(response, reverse("profile_settings"))
        self.driver_profile.refresh_from_db()
        self.assertTrue(self.driver_profile.profile_picture)

    def test_profile_picture_page_requires_login(self):
        response = self.client.get(reverse("profile_settings"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_invalid_file_is_rejected(self):
        self.client.force_login(self.customer)
        invalid_file = SimpleUploadedFile(
            "not-an-image.png",
            b"This is not a real image.",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("profile_settings"),
            {"profile_picture": invalid_file},
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.profile_picture)

    def test_oversized_image_is_rejected(self):
        self.client.force_login(self.customer)
        oversized = SimpleUploadedFile(
            "oversized.png",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/png",
        )

        response = self.client.post(
            reverse("profile_settings"),
            {"profile_picture": oversized},
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.profile_picture)
    def test_png_content_with_jpg_extension_is_accepted(self):
        from accounts.forms import ProfilePictureForm

        upload = self.make_image(name="profile.jpg")
        form = ProfilePictureForm(files={"profile_picture": upload})

        self.assertTrue(form.is_valid(), form.errors)

    def test_unsupported_gif_image_is_rejected(self):
        from accounts.forms import ProfilePictureForm

        upload = self.make_image(
            name="profile.gif",
            image_format="GIF",
        )
        form = ProfilePictureForm(files={"profile_picture": upload})

        self.assertFalse(form.is_valid())
        self.assertIn("profile_picture", form.errors)

    def test_image_exceeding_pixel_limit_is_rejected(self):
        from accounts.forms import ProfilePictureForm

        upload = self.make_image(
            name="large.png",
            size=(5001, 5000),
        )
        self.assertLessEqual(upload.size, 5 * 1024 * 1024)

        form = ProfilePictureForm(files={"profile_picture": upload})

        self.assertFalse(form.is_valid())
        self.assertIn("profile_picture", form.errors)
from pathlib import Path
from datetime import timedelta

from django.utils import timezone

from bookings.models import TransportRequest


class AssignedDriverRidesTests(TestCase):
    def setUp(self):
        self.approved_driver = self.create_driver(
            "approved_driver",
            UserProfile.DriverStatus.APPROVED,
        )
        self.second_driver = self.create_driver(
            "second_driver",
            UserProfile.DriverStatus.APPROVED,
        )
        self.pending_driver = self.create_driver(
            "pending_driver",
            UserProfile.DriverStatus.PENDING,
        )

        self.create_ride(
            self.approved_driver,
            "Bochum",
            "Polokwane",
        )
        self.create_ride(
            self.second_driver,
            "Witten",
            "Tzaneen",
        )

    def create_driver(self, username, driver_status):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="DriverTest!2026Secure",
        )
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "role": UserProfile.Role.DRIVER,
                "driver_status": driver_status,
            },
        )
        profile.role = UserProfile.Role.DRIVER
        profile.driver_status = driver_status
        profile.save()
        return user

    def create_ride(self, driver, pickup, destination):
        return TransportRequest.objects.create(
            assigned_driver=driver,
            customer_name="Test Passenger",
            contact_number="0712345678",
            pickup_location=pickup,
            destination=destination,
            travel_datetime=timezone.now() + timedelta(days=1),
            passenger_count=1,
        )

    def test_approved_driver_can_view_assigned_rides(self):
        self.client.force_login(self.approved_driver)

        response = self.client.get(
            reverse("assigned_driver_rides")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bochum")
        self.assertContains(response, "Polokwane")

    def test_unapproved_driver_cannot_view_assigned_rides(self):
        self.client.force_login(self.pending_driver)

        response = self.client.get(
            reverse("assigned_driver_rides")
        )

        self.assertRedirects(
            response,
            reverse("account_dashboard"),
        )

    def test_driver_cannot_see_another_drivers_rides(self):
        self.client.force_login(self.approved_driver)

        response = self.client.get(
            reverse("assigned_driver_rides")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bochum")
        self.assertContains(response, "Polokwane")
        self.assertNotContains(response, "Witten")
        self.assertNotContains(response, "Tzaneen")


class DriverRideAcceptanceTests(TestCase):
    def setUp(self):
        self.driver = self.make_user(
            "accepting_driver",
            UserProfile.Role.DRIVER,
            UserProfile.DriverStatus.APPROVED,
        )
        self.other_driver = self.make_user(
            "other_accepting_driver",
            UserProfile.Role.DRIVER,
            UserProfile.DriverStatus.APPROVED,
        )
        self.pending_driver = self.make_user(
            "unapproved_accepting_driver",
            UserProfile.Role.DRIVER,
            UserProfile.DriverStatus.PENDING,
        )
        self.customer = self.make_user(
            "acceptance_customer",
            UserProfile.Role.CUSTOMER,
            UserProfile.DriverStatus.NOT_APPLICABLE,
        )

        self.ride = self.make_ride(self.driver, "Bochum", "Polokwane")
        self.other_ride = self.make_ride(
            self.other_driver,
            "Witten",
            "Tzaneen",
        )

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

    def make_ride(self, driver, pickup, destination):
        return TransportRequest.objects.create(
            assigned_driver=driver,
            customer=self.customer if hasattr(self, "customer") else None,
            customer_name="Test Passenger",
            contact_number="0712345678",
            pickup_location=pickup,
            destination=destination,
            travel_datetime=timezone.now() + timedelta(days=1),
            proposed_fare="150.00",
            passenger_count=1,
        )

    def test_driver_can_accept_own_pending_ride(self):
        self.client.force_login(self.driver)

        response = self.client.post(
            reverse("accept_assigned_ride", args=[self.ride.pk])
        )

        self.assertRedirects(
            response,
            reverse("assigned_driver_rides"),
        )
        self.ride.refresh_from_db()
        self.assertEqual(
            self.ride.status,
            TransportRequest.Status.ACCEPTED,
        )

    def test_driver_cannot_accept_another_drivers_ride(self):
        self.client.force_login(self.driver)

        response = self.client.post(
            reverse("accept_assigned_ride", args=[self.other_ride.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.other_ride.refresh_from_db()
        self.assertEqual(
            self.other_ride.status,
            TransportRequest.Status.PENDING,
        )

    def test_driver_cannot_accept_ride_twice_or_change_accepted_status(self):
        self.ride.status = TransportRequest.Status.ACCEPTED
        self.ride.save(update_fields=["status"])
        self.client.force_login(self.driver)

        response = self.client.post(
            reverse("accept_assigned_ride", args=[self.ride.pk])
        )

        self.assertRedirects(
            response,
            reverse("assigned_driver_rides"),
        )
        self.ride.refresh_from_db()
        self.assertEqual(
            self.ride.status,
            TransportRequest.Status.ACCEPTED,
        )

    def test_get_request_cannot_accept_ride(self):
        self.client.force_login(self.driver)

        response = self.client.get(
            reverse("accept_assigned_ride", args=[self.ride.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.ride.refresh_from_db()
        self.assertEqual(
            self.ride.status,
            TransportRequest.Status.PENDING,
        )

    def test_unapproved_driver_cannot_accept_ride(self):
        self.client.force_login(self.pending_driver)

        response = self.client.post(
            reverse("accept_assigned_ride", args=[self.ride.pk])
        )

        self.assertRedirects(
            response,
            reverse("account_dashboard"),
        )
        self.ride.refresh_from_db()
        self.assertEqual(
            self.ride.status,
            TransportRequest.Status.PENDING,
        )

    def test_customer_cannot_accept_driver_ride(self):
        self.client.force_login(self.customer)

        response = self.client.post(
            reverse("accept_assigned_ride", args=[self.ride.pk])
        )

        self.assertRedirects(
            response,
            reverse("account_dashboard"),
        )
        self.ride.refresh_from_db()
        self.assertEqual(
            self.ride.status,
            TransportRequest.Status.PENDING,
        )

class DriverRideCompletionTests(TestCase):
    def make_user(self, username, role, driver_status=None):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="CompletionTest!2026",
        )
        profile_data = {"role": role}
        if driver_status is not None:
            profile_data["driver_status"] = driver_status
        UserProfile.objects.create(user=user, **profile_data)
        return user

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone

        self.driver = self.make_user(
            "completion_driver",
            UserProfile.Role.DRIVER,
            UserProfile.DriverStatus.APPROVED,
        )
        self.other_driver = self.make_user(
            "completion_other_driver",
            UserProfile.Role.DRIVER,
            UserProfile.DriverStatus.APPROVED,
        )
        self.customer = self.make_user(
            "completion_customer",
            UserProfile.Role.CUSTOMER,
        )
        self.ride = self.create_ride(
            self.driver,
            TransportRequest.Status.CONFIRMED,
        )
        self.other_ride = self.create_ride(
            self.other_driver,
            TransportRequest.Status.CONFIRMED,
        )

    def create_ride(self, driver, status):
        from datetime import timedelta
        from django.utils import timezone

        return TransportRequest.objects.create(
            customer=self.customer if hasattr(self, "customer") else None,
            assigned_driver=driver,
            customer_name="Test Passenger",
            contact_number="0712345678",
            pickup_location="Soweto",
            destination="Johannesburg",
            travel_datetime=timezone.now() + timedelta(days=1),
            passenger_count=1,
            status=status,
            proposed_fare="150.00",
            agreed_fare="150.00" if status in (
                TransportRequest.Status.CONFIRMED,
                TransportRequest.Status.COMPLETED,
            ) else None,
        )

    def test_assigned_driver_can_complete_confirmed_ride(self):
        from django.utils import timezone

        self.ride.travel_datetime = timezone.now() - timedelta(minutes=1)
        self.ride.save(update_fields=["travel_datetime"])
        self.client.force_login(self.driver)
        response = self.client.post(
            reverse("complete_assigned_ride", args=[self.ride.pk])
        )
        self.assertRedirects(response, reverse("assigned_driver_rides"))
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, TransportRequest.Status.COMPLETED)

    def test_completing_ride_stops_and_clears_live_location(self):
        from bookings.models import DriverLiveLocation
        from django.utils import timezone
        from datetime import timedelta

        self.ride.travel_datetime = timezone.now() - timedelta(minutes=1)
        self.ride.save(update_fields=["travel_datetime"])

        location = DriverLiveLocation.objects.create(
            ride=self.ride,
            driver=self.driver,
            latitude=-23.900000,
            longitude=29.400000,
            is_sharing=True,
        )

        self.client.force_login(self.driver)
        response = self.client.post(
            reverse("complete_assigned_ride", args=[self.ride.pk])
        )

        self.assertRedirects(response, reverse("assigned_driver_rides"))

        self.ride.refresh_from_db()
        location.refresh_from_db()

        self.assertEqual(self.ride.status, TransportRequest.Status.COMPLETED)
        self.assertFalse(location.is_sharing)
        self.assertIsNone(location.latitude)
        self.assertIsNone(location.longitude)

    def test_future_confirmed_ride_cannot_be_completed_early(self):
        self.client.force_login(self.driver)
        response = self.client.post(
            reverse("complete_assigned_ride", args=[self.ride.pk])
        )
        self.assertRedirects(response, reverse("assigned_driver_rides"))
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, TransportRequest.Status.CONFIRMED)
        self.assertContains(
            self.client.get(reverse("assigned_driver_rides")),
            "Complete ride",
            count=0,
        )

    def test_driver_cannot_complete_another_drivers_ride(self):
        self.client.force_login(self.driver)
        response = self.client.post(
            reverse("complete_assigned_ride", args=[self.other_ride.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.other_ride.refresh_from_db()
        self.assertEqual(
            self.other_ride.status,
            TransportRequest.Status.CONFIRMED,
        )

    def test_pending_ride_cannot_be_completed(self):
        pending = self.create_ride(
            self.driver,
            TransportRequest.Status.PENDING,
        )
        self.client.force_login(self.driver)
        response = self.client.post(
            reverse("complete_assigned_ride", args=[pending.pk])
        )
        self.assertRedirects(response, reverse("assigned_driver_rides"))
        pending.refresh_from_db()
        self.assertEqual(pending.status, TransportRequest.Status.PENDING)

    def test_accepted_ride_cannot_be_completed_before_customer_confirmation(self):
        accepted = self.create_ride(
            self.driver,
            TransportRequest.Status.ACCEPTED,
        )
        self.client.force_login(self.driver)
        response = self.client.post(
            reverse("complete_assigned_ride", args=[accepted.pk])
        )
        self.assertRedirects(response, reverse("assigned_driver_rides"))
        accepted.refresh_from_db()
        self.assertEqual(accepted.status, TransportRequest.Status.ACCEPTED)

    def test_completed_ride_cannot_be_completed_again(self):
        completed = self.create_ride(
            self.driver,
            TransportRequest.Status.COMPLETED,
        )
        self.client.force_login(self.driver)
        response = self.client.post(
            reverse("complete_assigned_ride", args=[completed.pk])
        )
        self.assertRedirects(response, reverse("assigned_driver_rides"))
        completed.refresh_from_db()
        self.assertEqual(completed.status, TransportRequest.Status.COMPLETED)

    def test_get_request_is_not_allowed(self):
        self.client.force_login(self.driver)
        response = self.client.get(
            reverse("complete_assigned_ride", args=[self.ride.pk])
        )
        self.assertEqual(response.status_code, 405)
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, TransportRequest.Status.CONFIRMED)

    def test_unapproved_driver_cannot_complete_ride(self):
        unapproved = self.make_user(
            "completion_unapproved_driver",
            UserProfile.Role.DRIVER,
            UserProfile.DriverStatus.PENDING,
        )
        ride = self.create_ride(
            unapproved,
            TransportRequest.Status.CONFIRMED,
        )
        self.client.force_login(unapproved)
        response = self.client.post(
            reverse("complete_assigned_ride", args=[ride.pk])
        )
        self.assertRedirects(response, reverse("account_dashboard"))
        ride.refresh_from_db()
        self.assertEqual(ride.status, TransportRequest.Status.CONFIRMED)

    def test_customer_cannot_complete_ride(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("complete_assigned_ride", args=[self.ride.pk])
        )
        self.assertRedirects(response, reverse("account_dashboard"))
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, TransportRequest.Status.CONFIRMED)

    def test_confirmed_ride_shows_completion_button(self):
        from django.utils import timezone

        self.ride.travel_datetime = timezone.now() - timedelta(minutes=1)
        self.ride.save(update_fields=["travel_datetime"])
        self.client.force_login(self.driver)
        response = self.client.get(reverse("assigned_driver_rides"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Complete ride")
