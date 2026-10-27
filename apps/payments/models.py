from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Order created"
        PAID = "paid", "Paid (held in escrow)"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        RELEASED = "released", "Released to provider"

    booking = models.OneToOneField("bookings.Booking", on_delete=models.CASCADE, related_name="payment")
    razorpay_order_id = models.CharField(max_length=64, unique=True)
    razorpay_payment_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CREATED)
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    commission = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    provider_payout = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    is_mock = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.razorpay_order_id} [{self.status}]"


class WebhookEvent(models.Model):
    """Stores processed webhook ids -> makes webhook handling idempotent."""
    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=60)
    received_at = models.DateTimeField(auto_now_add=True)
