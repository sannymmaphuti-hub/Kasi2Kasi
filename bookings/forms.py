from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from .models import TransportRequest


class TransportRequestForm(forms.ModelForm):
    pickup_latitude = forms.DecimalField(
        required=False,
        min_value=-90,
        max_value=90,
        widget=forms.HiddenInput(),
    )
    pickup_longitude = forms.DecimalField(
        required=False,
        min_value=-180,
        max_value=180,
        widget=forms.HiddenInput(),
    )
    destination_latitude = forms.DecimalField(
        required=False,
        min_value=-90,
        max_value=90,
        widget=forms.HiddenInput(),
    )
    destination_longitude = forms.DecimalField(
        required=False,
        min_value=-180,
        max_value=180,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = TransportRequest
        fields = [
            "customer_name",
            "contact_number",
            "pickup_location",
            "pickup_latitude",
            "pickup_longitude",
            "destination",
            "destination_latitude",
            "destination_longitude",
            "travel_datetime",
            "passenger_count",
            "additional_notes",
        ]

        widgets = {
            "customer_name": forms.TextInput(attrs={
                "placeholder": "Your full name",
                "autocomplete": "name",
            }),
            "contact_number": forms.TextInput(attrs={
                "placeholder": "e.g. 071 234 5678",
                "type": "tel",
                "autocomplete": "tel",
            }),
            "pickup_location": forms.TextInput(attrs={
                "placeholder": "Where should we pick you up?",
            }),
            "destination": forms.TextInput(attrs={
                "placeholder": "Where are you going?",
            }),
            "travel_datetime": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "passenger_count": forms.NumberInput(attrs={
                "min": 1,
                "max": 20,
            }),
            "additional_notes": forms.Textarea(attrs={
                "placeholder": "Optional travel details",
                "rows": 3,
            }),
        }

    def clean_travel_datetime(self):
        travel_datetime = self.cleaned_data["travel_datetime"]

        if travel_datetime <= timezone.localtime():
            raise forms.ValidationError(
                "Please choose a future date and time."
            )

        return travel_datetime

    def clean_passenger_count(self):
        count = self.cleaned_data["passenger_count"]

        if not 1 <= count <= 20:
            raise forms.ValidationError(
                "Passenger count must be between 1 and 20."
            )

        return count

    def clean(self):
        cleaned_data = super().clean()

        coordinate_pairs = (
            (
                "pickup_latitude",
                "pickup_longitude",
                "Pickup",
            ),
            (
                "destination_latitude",
                "destination_longitude",
                "Destination",
            ),
        )

        for latitude_field, longitude_field, label in coordinate_pairs:
            latitude = cleaned_data.get(latitude_field)
            longitude = cleaned_data.get(longitude_field)

            if (latitude is None) != (longitude is None):
                self.add_error(
                    latitude_field,
                    f"Select a complete map location for {label.lower()}, "
                    "or leave both coordinates empty.",
                )

        return cleaned_data
