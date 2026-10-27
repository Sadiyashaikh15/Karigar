from django.contrib import admin

from .models import Availability, Category, ProviderProfile, Service, TimeOff


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon")
    prepopulated_fields = {"slug": ("name",)}


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "city", "is_verified", "is_suspended", "avg_rating",
                    "rating_count", "completed_jobs")
    list_filter = ("is_verified", "is_suspended", "city")
    search_fields = ("user__username", "user__email", "city")
    actions = ["verify", "suspend", "unsuspend"]
    inlines = [ServiceInline]

    @admin.action(description="Verify selected providers")
    def verify(self, request, qs):
        qs.update(is_verified=True)

    @admin.action(description="Suspend selected providers")
    def suspend(self, request, qs):
        qs.update(is_suspended=True)

    @admin.action(description="Un-suspend selected providers")
    def unsuspend(self, request, qs):
        qs.update(is_suspended=False)


admin.site.register(Service)
admin.site.register(Availability)
admin.site.register(TimeOff)
