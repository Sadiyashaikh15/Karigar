from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    booking = models.OneToOneField("bookings.Booking", on_delete=models.CASCADE, related_name="review")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, max_length=1000)
    is_flagged = models.BooleanField(default=False, help_text="Reported by a user / auto-flagged")
    is_hidden = models.BooleanField(default=False, help_text="Hidden by admin moderation")
    report_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review#{self.pk} {self.rating}★ booking={self.booking_id}"
