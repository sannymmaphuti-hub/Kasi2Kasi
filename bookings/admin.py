from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.html import format_html

from accounts.models import UserProfile
from .models import TransportRequest


User = get_user_model()


class TransportRequestAdminForm(forms.ModelForm):
    """Validate driver assignments and fare information in the admin."""

    class Meta:
        model = TransportRequest
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        approved_drivers = User.objects.filter(
            profile__role=UserProfile.Role.DRIVER,
            profile__driver_status=UserProfile.DriverStatus.APPROVED,
        )

        # Keep an existing assignment selectable even if that driver's
        # approval status changed, so the operator can correct it.
        if self.instance and self.instance.pk:
            existing_driver_id = self.instance.assigned_driver_id

            if existing_driver_id:
                approved_drivers = approved_drivers | User.objects.filter(
                    pk=existing_driver_id
                )

        self.fields["assigned_driver"].queryset = approved_drivers.distinct()
        self.fields["assigned_driver"].required = False
        self.fields["proposed_fare"].required = False
        self.fields["agreed_fare"].required = False

    def clean(self):
        cleaned_data = super().clean()

        driver = cleaned_data.get("assigned_driver")
        proposed_fare = cleaned_data.get("proposed_fare")
        agreed_fare = cleaned_data.get("agreed_fare")

        if driver:
            try:
                profile = driver.profile
            except UserProfile.DoesNotExist:
                self.add_error(
                    "assigned_driver",
                    "The selected driver does not have a profile.",
                )
            else:
                if (
                    profile.role != UserProfile.Role.DRIVER
                    or profile.driver_status
                    != UserProfile.DriverStatus.APPROVED
                ):
                    # Permit an unchanged legacy assignment so it can be
                    # reviewed or replaced; do not allow a new invalid one.
                    if driver.pk != self.instance.assigned_driver_id:
                        self.add_error(
                            "assigned_driver",
                            "Only approved driver accounts may be assigned.",
                        )

        for field_name, fare in (
            ("proposed_fare", proposed_fare),
            ("agreed_fare", agreed_fare),
        ):
            if fare is not None and fare <= 0:
                self.add_error(
                    field_name,
                    "The fare must be greater than zero.",
                )

        if agreed_fare is not None and proposed_fare is None:
            self.add_error(
                "agreed_fare",
                "Enter a proposed fare before recording an agreed fare.",
            )

        return cleaned_data


@admin.register(TransportRequest)
class TransportRequestAdmin(admin.ModelAdmin):
    form = TransportRequestAdminForm

    list_display = (
        "customer_name",
        "customer_account",
        "pickup_location",
        "pickup_map",
        "destination",
        "destination_map",
        "travel_datetime",
        "passenger_count",
        "assigned_driver",
        "proposed_fare",
        "agreed_fare",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "assigned_driver",
        "travel_datetime",
        "created_at",
    )

    search_fields = (
        "customer_name",
        "contact_number",
        "customer__username",
        "customer__email",
        "assigned_driver__username",
        "assigned_driver__email",
        "pickup_location",
        "destination",
    )

    list_editable = ("status",)
    list_per_page = 25
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    readonly_fields = (
        "created_at",
        "pickup_map_link",
        "destination_map_link",
    )

    fieldsets = (
        (
            "Passenger information",
            {
                "fields": (
                    "customer",
                    "customer_name",
                    "contact_number",
                    "passenger_count",
                ),
            },
        ),
        (
            "Pickup location",
            {
                "fields": (
                    "pickup_location",
                    "pickup_latitude",
                    "pickup_longitude",
                    "pickup_map_link",
                ),
            },
        ),
        (
            "Destination",
            {
                "fields": (
                    "destination",
                    "destination_latitude",
                    "destination_longitude",
                    "destination_map_link",
                ),
            },
        ),
        (
            "Journey details",
            {
                "fields": (
                    "travel_datetime",
                    "additional_notes",
                ),
            },
        ),
        (
            "Driver assignment and fares",
            {
                "description": (
                    "Assign an approved driver and record the proposed "
                    "and agreed fares. Leave the agreed fare empty until "
                    "the customer has accepted the price."
                ),
                "fields": (
                    "assigned_driver",
                    "proposed_fare",
                    "agreed_fare",
                ),
            },
        ),
        (
            "Booking management",
            {
                "fields": (
                    "status",
                    "created_at",
                ),
            },
        ),
    )

    @admin.display(description="Customer account", ordering="customer__username")
    def customer_account(self, obj):
        if obj.customer is None:
            return "Unassigned / legacy booking"

        return obj.customer.username

    @staticmethod
    def _map_link(latitude, longitude, label):
        if latitude is None or longitude is None:
            return "No map coordinates available"

        url = (
            "https://www.openstreetmap.org/"
            f"?mlat={latitude}&mlon={longitude}"
            f"#map=17/{latitude}/{longitude}"
        )

        return format_html(
            '<a href="{}" target="_blank" '
            'rel="noopener noreferrer">{}</a>',
            url,
            label,
        )

    @admin.display(description="Pickup map")
    def pickup_map(self, obj):
        return self._map_link(
            obj.pickup_latitude,
            obj.pickup_longitude,
            "View pickup",
        )

    @admin.display(description="Destination map")
    def destination_map(self, obj):
        return self._map_link(
            obj.destination_latitude,
            obj.destination_longitude,
            "View destination",
        )

    @admin.display(description="Open pickup location")
    def pickup_map_link(self, obj):
        return self._map_link(
            obj.pickup_latitude,
            obj.pickup_longitude,
            "Open pickup in OpenStreetMap",
        )

    @admin.display(description="Open destination")
    def destination_map_link(self, obj):
        return self._map_link(
            obj.destination_latitude,
            obj.destination_longitude,
            "Open destination in OpenStreetMap",
        )