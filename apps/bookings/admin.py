from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "provider", "service", "start", "status", "amount")
    list_filter = ("status",)
    search_fields = ("customer__username", "provider__user__username")
    date_hierarchy = "start"
