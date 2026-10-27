from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import IsCustomer

from .models import Review
from .serializers import ReviewCreateSerializer
from .utils import recompute_provider_rating


class ReviewListCreateView(APIView):
    throttle_scope = "review"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsCustomer()]

    def get_throttles(self):
        # only throttle writes with the strict scope
        return super().get_throttles() if self.request.method == "POST" else []

    def get(self, request):
        qs = Review.objects.filter(is_hidden=False).select_related("booking__customer")
        if request.query_params.get("provider"):
            qs = qs.filter(booking__provider_id=request.query_params["provider"])
        return Response([
            {"id": r.id, "rating": r.rating, "comment": r.comment,
             "customer": r.booking.customer.first_name or r.booking.customer.username,
             "created_at": r.created_at}
            for r in qs.order_by("-created_at")[:50]
        ])

    def post(self, request):
        s = ReviewCreateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        b = s.validated_data["booking"]
        review = Review.objects.create(
            booking=b, rating=s.validated_data["rating"], comment=s.validated_data["comment"]
        )
        recompute_provider_rating(b.provider)
        return Response({"id": review.id, "rating": review.rating}, status=status.HTTP_201_CREATED)


class ReportReviewView(APIView):
    """Providers (or anyone logged in) can report an abusive review -> admin moderation queue."""

    def post(self, request, pk):
        try:
            r = Review.objects.get(pk=pk)
        except Review.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        r.is_flagged = True
        r.report_reason = str(request.data.get("reason", ""))[:200]
        r.save(update_fields=["is_flagged", "report_reason"])
        return Response({"status": "reported"})
