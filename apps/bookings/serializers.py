from rest_framework import serializers

from apps.providers.models import Service

from .models import Booking


class BookingCreateSerializer(serializers.Serializer):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    start = serializers.DateTimeField()
    address = serializers.CharField(max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class BookingSerializer(serializers.ModelSerializer):
    service_title = serializers.CharField(source="service.title", read_only=True)
    provider_name = serializers.CharField(source="provider.display_name", read_only=True)
    provider_id = serializers.IntegerField(read_only=True)
    customer_name = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    has_review = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            "id", "service", "service_title", "provider_id", "provider_name", "customer",
            "customer_name", "start", "end", "status", "address", "notes", "amount",
            "commission", "payment_status", "has_review", "created_at",
        )

    def get_customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username

    def get_payment_status(self, obj):
        p = getattr(obj, "payment", None)
        return p.status if p else None

    def get_has_review(self, obj):
        return hasattr(obj, "review")
