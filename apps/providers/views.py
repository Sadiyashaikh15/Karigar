from datetime import date as date_cls

from django.db.models import Q
from rest_framework import generics, mixins, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.slots import get_free_slots
from apps.reviews.models import Review
from apps.users.permissions import IsProvider

from .geo import bounding_box, haversine_km
from .models import Availability, Category, ProviderProfile, Service, TimeOff
from .serializers import (
    AvailabilitySerializer, CategorySerializer, MyProfileSerializer,
    ProviderCardSerializer, ServiceSerializer, TimeOffSerializer,
)


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None


class ProviderSearchView(APIView):
    """GET /api/providers/?category=&q=&lat=&lng=&radius=&min_rating=&max_price=&sort=&page="""
    permission_classes = [AllowAny]

    def get(self, request):
        p = request.query_params
        qs = (
            ProviderProfile.objects.filter(is_suspended=False, services__is_active=True)
            .select_related("user")
            .prefetch_related("services")
            .distinct()
        )
        if p.get("category"):
            qs = qs.filter(services__category__slug=p["category"])
        if p.get("q"):
            q = p["q"]
            qs = qs.filter(
                Q(services__title__icontains=q) | Q(user__first_name__icontains=q)
                | Q(user__username__icontains=q) | Q(bio__icontains=q)
                | Q(services__category__name__icontains=q)
            )
        try:
            if p.get("min_rating"):
                qs = qs.filter(avg_rating__gte=float(p["min_rating"]))
            if p.get("max_price"):
                qs = qs.filter(services__price__lte=float(p["max_price"]))
        except ValueError:
            pass
        if p.get("verified") == "1":
            qs = qs.filter(is_verified=True)

        lat = lng = radius = None
        try:
            lat, lng = float(p["lat"]), float(p["lng"])
            radius = float(p.get("radius", 15))
        except (KeyError, ValueError):
            lat = lng = radius = None

        if lat is not None:
            s, n, w, e = bounding_box(lat, lng, radius)
            qs = qs.filter(latitude__gte=s, latitude__lte=n, longitude__gte=w, longitude__lte=e)

        results = []
        for prof in qs.distinct():
            dist = None
            if lat is not None and prof.latitude is not None:
                dist = haversine_km(lat, lng, prof.latitude, prof.longitude)
                if dist > radius:
                    continue
            results.append((prof, dist))

        sort = p.get("sort", "best" if lat is not None else "rating")
        if sort == "distance" and lat is not None:
            results.sort(key=lambda r: r[1] if r[1] is not None else 1e9)
        elif sort == "price":
            results.sort(key=lambda r: min(s.price for s in r[0].services.all()))
        elif sort == "rating":
            results.sort(key=lambda r: (-r[0].avg_rating, -r[0].rating_count))
        else:  # smart ranking: distance + rating + completion rate + verification
            def score(r):
                prof, d = r
                rad = radius or 15
                dist_score = 1 - min((d if d is not None else rad) / rad, 1)
                return (
                    0.4 * dist_score + 0.35 * (prof.avg_rating / 5)
                    + 0.15 * prof.completion_rate + 0.10 * (1 if prof.is_verified else 0)
                )
            results.sort(key=score, reverse=True)

        try:
            page = max(int(p.get("page", 1)), 1)
            size = min(max(int(p.get("page_size", 12)), 1), 50)
        except ValueError:
            page, size = 1, 12
        total = len(results)
        data = []
        for prof, dist in results[(page - 1) * size: page * size]:
            item = ProviderCardSerializer(prof).data
            item["distance_km"] = round(dist, 1) if dist is not None else None
            data.append(item)
        return Response({"count": total, "page": page, "page_size": size, "results": data})


class ProviderDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            prof = ProviderProfile.objects.select_related("user").prefetch_related(
                "services", "availability"
            ).get(pk=pk, is_suspended=False)
        except ProviderProfile.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        data = ProviderCardSerializer(prof).data
        data["availability"] = [
            {"day_of_week": a.day_of_week, "day_name": a.get_day_of_week_display(),
             "start_time": a.start_time.strftime("%H:%M"), "end_time": a.end_time.strftime("%H:%M")}
            for a in prof.availability.all()
        ]
        reviews = Review.objects.filter(booking__provider=prof, is_hidden=False).select_related(
            "booking__customer"
        ).order_by("-created_at")[:10]
        data["reviews"] = [
            {"id": r.id, "rating": r.rating, "comment": r.comment,
             "customer": r.booking.customer.first_name or r.booking.customer.username,
             "created_at": r.created_at}
            for r in reviews
        ]
        return Response(data)


class ProviderSlotsView(APIView):
    """GET /api/providers/<id>/slots/?service=<id>&date=YYYY-MM-DD"""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            service = Service.objects.select_related("provider").get(
                pk=request.query_params.get("service"), provider_id=pk, is_active=True
            )
            day = date_cls.fromisoformat(request.query_params.get("date", ""))
        except (Service.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Provide valid service and date (YYYY-MM-DD)"}, status=400)
        slots = get_free_slots(service.provider, service, day)
        return Response({"date": day.isoformat(), "slots": [s.isoformat() for s in slots]})


# ---------- provider's own management endpoints ----------
class MyProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = MyProfileSerializer
    permission_classes = [IsProvider]

    def get_object(self):
        return self.request.user.provider_profile


class OwnedByProviderMixin:
    permission_classes = [IsProvider]

    def perform_create(self, serializer):
        serializer.save(provider=self.request.user.provider_profile)


class MyServiceViewSet(OwnedByProviderMixin, viewsets.ModelViewSet):
    serializer_class = ServiceSerializer
    pagination_class = None

    def get_queryset(self):
        return Service.objects.filter(provider=self.request.user.provider_profile)


class MyAvailabilityViewSet(OwnedByProviderMixin, mixins.CreateModelMixin, mixins.ListModelMixin,
                            mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = AvailabilitySerializer
    pagination_class = None

    def get_queryset(self):
        return Availability.objects.filter(provider=self.request.user.provider_profile)


class MyTimeOffViewSet(OwnedByProviderMixin, mixins.CreateModelMixin, mixins.ListModelMixin,
                       mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = TimeOffSerializer
    pagination_class = None

    def get_queryset(self):
        return TimeOff.objects.filter(provider=self.request.user.provider_profile)
