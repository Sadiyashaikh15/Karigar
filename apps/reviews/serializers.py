from rest_framework import serializers

from apps.bookings.models import Booking

from .models import Review
from .utils import contains_profanity


class ReviewCreateSerializer(serializers.Serializer):
    booking = serializers.PrimaryKeyRelatedField(queryset=Booking.objects.all())
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=1000, default="")

    def validate(self, data):
        user = self.context["request"].user
        b = data["booking"]
        if b.customer_id != user.id:
            raise serializers.ValidationError("You can only review your own bookings.")
        if b.status != "completed":
            raise serializers.ValidationError("You can review only after the job is completed.")
        if Review.objects.filter(booking=b).exists():
            raise serializers.ValidationError("You already reviewed this booking.")
        if contains_profanity(data.get("comment")):
            raise serializers.ValidationError({"comment": "Please keep the review respectful."})
        return data
