from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


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

        if image:
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError(
                    "The profile picture must be 5 MB or smaller."
                )

        return image
