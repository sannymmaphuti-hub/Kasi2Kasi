from django.contrib import admin, messages

from .models import DriverVehicle, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "driver_status",
        "created_at",
            "is_available",
    )

    list_filter = (
        "role",
        "driver_status",
        "created_at",
            "is_available",
    )

    search_fields = (
        "user__username",
        "user__email",
    )

    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    actions = (
        "approve_drivers",
        "reject_drivers",
        "suspend_drivers",
    )

    @admin.action(description="Approve selected driver accounts")
    def approve_drivers(self, request, queryset):
        updated = self._set_driver_status(
            queryset,
            UserProfile.DriverStatus.APPROVED,
        )
        self.message_user(
            request,
            f"{updated} driver account(s) approved.",
            messages.SUCCESS,
        )

    @admin.action(description="Reject selected driver accounts")
    def reject_drivers(self, request, queryset):
        updated = self._set_driver_status(
            queryset,
            UserProfile.DriverStatus.REJECTED,
        )
        self.message_user(
            request,
            f"{updated} driver account(s) rejected.",
            messages.WARNING,
        )

    @admin.action(description="Suspend selected driver accounts")
    def suspend_drivers(self, request, queryset):
        updated = self._set_driver_status(
            queryset,
            UserProfile.DriverStatus.SUSPENDED,
        )
        self.message_user(
            request,
            f"{updated} driver account(s) suspended.",
            messages.WARNING,
        )

    @staticmethod
    def _set_driver_status(queryset, status):
        # Never change customer profiles through driver actions.
        # Every admin status action leaves drivers offline. Drivers
        # must explicitly go online after their account is approved.
        drivers = queryset.filter(role=UserProfile.Role.DRIVER)
        return drivers.update(
            driver_status=status,
            is_available=False,
        )

@admin.register(DriverVehicle)
class DriverVehicleAdmin(admin.ModelAdmin):
    list_display = (
        "registration_number",
        "driver",
        "vehicle_type",
        "make",
        "model",
        "is_active",
        "verified",
        "created_at",
    )
    list_filter = ("vehicle_type", "is_active", "verified", "created_at")
    search_fields = (
        "registration_number",
        "make",
        "model",
        "driver__username",
        "driver__email",
    )
    list_editable = ("is_active", "verified")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

