from django import forms
from django.contrib.auth.forms import UserCreationForm
import warnings

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from PIL import Image, UnidentifiedImageError


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label="First name",
    )

    last_name = forms.CharField(
        max_length=150,
        required=True,
        label="Last name",
    )

    email = forms.EmailField(
        required=True,
        label="Email address",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.email = self.cleaned_data["email"].strip().lower()

        if commit:
            user.save()

        return user


from .models import UserProfile


class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("profile_picture",)
        labels = {
            "profile_picture": "Profile picture",
        }
        help_texts = {
            "profile_picture": "Upload an image no larger than 5 MB.",
        }

    def clean_profile_picture(self):
        image = self.cleaned_data.get("profile_picture")

        if not image:
            return image

        if image.size > 5 * 1024 * 1024:
            raise forms.ValidationError(
                "The profile picture must be 5 MB or smaller."
            )

        allowed_formats = {"JPEG", "PNG", "WEBP"}
        max_pixels = 25_000_000

        try:
            image.seek(0)

            # Treat Pillow's decompression-bomb warning as a validation
            # failure rather than allowing suspicious images through.
            with warnings.catch_warnings():
                warnings.simplefilter(
                    "error",
                    Image.DecompressionBombWarning,
                )

                with Image.open(image) as decoded:
                    if decoded.format not in allowed_formats:
                        raise forms.ValidationError(
                            "Upload a JPEG, PNG, or WebP image."
                        )

                    width, height = decoded.size
                    if width * height > max_pixels:
                        raise forms.ValidationError(
                            "The image dimensions must not exceed "
                            "25 million pixels."
                        )

                    decoded.verify()

                # verify() checks file integrity but does not fully decode
                # pixels, so reopen the file and force a complete decode.
                image.seek(0)
                with Image.open(image) as decoded:
                    decoded.load()

        except forms.ValidationError:
            raise
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            raise forms.ValidationError(
                "The uploaded file is not a valid, supported image."
            ) from exc
        finally:
            image.seek(0)

        return image
