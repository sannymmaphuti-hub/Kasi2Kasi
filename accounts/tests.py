from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import UserProfile


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
            self.registration_data(
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
