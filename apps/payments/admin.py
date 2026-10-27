from django.contrib import admin

from .models import Payment, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("razorpay_order_id", "booking", "status", "amount", "commission", "is_mock")
    list_filter = ("status", "is_mock")


admin.site.register(WebhookEvent)
