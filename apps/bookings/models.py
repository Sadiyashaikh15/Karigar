from django.conf import settings
from django.db import models


class Booking(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        ACCEPTED = "accepted", "Accepted (awaiting payment)"
        PAID = "paid", "Paid"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        REJECTED = "rejected", "Rejected"

    ACTIVE_STATUSES = ("requested", "accepted", "paid", "in_progress")

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings"
    )
    provider = models.ForeignKey(
        "providers.ProviderProfile", on_delete=models.CASCADE, related_name="bookings"
    )
    service = models.ForeignKey("providers.Service", on_delete=models.PROTECT, related_name="bookings")
    start = models.DateTimeField(db_index=True)
    end = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    address = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    commission = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start"]
        indexes = [models.Index(fields=["provider", "start", "end"])]

    def __str__(self):
        return f"Booking#{self.pk} {self.service.title} {self.start:%d %b %H:%M} [{self.status}]"
