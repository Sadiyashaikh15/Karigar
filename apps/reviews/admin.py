from django.contrib import admin

from .models import Review
from .utils import recompute_provider_rating


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "rating", "is_flagged", "is_hidden", "created_at")
    list_filter = ("is_flagged", "is_hidden", "rating")
    actions = ["hide", "unhide"]

    @admin.action(description="Hide selected reviews (moderation)")
    def hide(self, request, qs):
        for r in qs.select_related("booking__provider"):
            r.is_hidden = True
            r.save(update_fields=["is_hidden"])
            recompute_provider_rating(r.booking.provider)

    @admin.action(description="Unhide selected reviews")
    def unhide(self, request, qs):
        for r in qs.select_related("booking__provider"):
            r.is_hidden = False
            r.is_flagged = False
            r.save(update_fields=["is_hidden", "is_flagged"])
            recompute_provider_rating(r.booking.provider)
