from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.permissions import IsCustomer

from . import services
from .models import Booking
from .serializers import BookingCreateSerializer, BookingSerializer


class BookingViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = BookingSerializer
    pagination_class = None

    def get_queryset(self):
        u = self.request.user
        qs = Booking.objects.select_related("service", "provider__user", "customer")
        if u.role == "provider":
            qs = qs.filter(provider__user=u)
        elif u.role == "customer":
            qs = qs.filter(customer=u)
        elif u.role != "admin":
            qs = qs.none()
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params["status"])
        return qs

    def create(self, request):
        if request.user.role != "customer":
            return Response({"detail": "Only customers can book."}, status=403)
        s = BookingCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            booking = services.create_booking(request.user, **s.validated_data)
        except services.SlotUnavailable as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        except services.BookingError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BookingSerializer(booking).data, status=201)

    def _do(self, fn, pk):
        try:
            booking = fn(int(pk), self.request.user)
        except Booking.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)
        except services.BookingError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(BookingSerializer(booking).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return self._do(services.accept, pk)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._do(services.reject, pk)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        return self._do(services.start_job, pk)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._do(services.complete, pk)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._do(services.cancel, pk)
