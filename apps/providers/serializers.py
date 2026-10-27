from rest_framework import serializers

from .models import Availability, Category, ProviderProfile, Service, TimeOff


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "icon")


class ServiceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Service
        fields = (
            "id", "category", "category_name", "title", "description",
            "price", "duration_minutes", "is_active",
        )


class AvailabilitySerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source="get_day_of_week_display", read_only=True)

    class Meta:
        model = Availability
        fields = ("id", "day_of_week", "day_name", "start_time", "end_time")

    def validate(self, data):
        if data["start_time"] >= data["end_time"]:
            raise serializers.ValidationError("end_time must be after start_time")
        provider = self.context["request"].user.provider_profile
        overlap = Availability.objects.filter(
            provider=provider,
            day_of_week=data["day_of_week"],
            start_time__lt=data["end_time"],
            end_time__gt=data["start_time"],
        )
        if overlap.exists():
            raise serializers.ValidationError("Overlaps an existing availability window")
        return data


class TimeOffSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeOff
        fields = ("id", "date", "reason")

    def validate_date(self, value):
        provider = self.context["request"].user.provider_profile
        if TimeOff.objects.filter(provider=provider, date=value).exists():
            raise serializers.ValidationError("Already marked as time off")
        return value


class MyProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    name = serializers.CharField(source="display_name", read_only=True)

    class Meta:
        model = ProviderProfile
        fields = (
            "id", "username", "name", "bio", "experience_years", "city", "latitude",
            "longitude", "service_radius_km", "is_verified", "avg_rating", "rating_count",
            "completed_jobs",
        )
        read_only_fields = ("is_verified", "avg_rating", "rating_count", "completed_jobs")


class ProviderCardSerializer(serializers.ModelSerializer):
    """Public representation used in search results & detail."""
    name = serializers.CharField(source="display_name", read_only=True)
    services = serializers.SerializerMethodField()

    class Meta:
        model = ProviderProfile
        fields = (
            "id", "name", "bio", "experience_years", "city", "latitude", "longitude",
            "service_radius_km", "is_verified", "avg_rating", "rating_count",
            "completed_jobs", "services",
        )

    def get_services(self, obj):
        qs = [s for s in obj.services.all() if s.is_active]
        return ServiceSerializer(qs, many=True).data
