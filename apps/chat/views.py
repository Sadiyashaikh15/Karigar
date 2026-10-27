from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking

from .models import Message


class MessageHistoryView(APIView):
    def get(self, request, booking_id):
        allowed = Booking.objects.filter(pk=booking_id).filter(
            customer=request.user
        ).exists() or Booking.objects.filter(pk=booking_id, provider__user=request.user).exists()
        if not allowed:
            return Response({"detail": "Not found"}, status=404)
        msgs = Message.objects.filter(booking_id=booking_id).select_related("sender")[:200]
        return Response([
            {"id": m.id, "sender": m.sender_id, "sender_name": m.sender.get_full_name() or m.sender.username,
             "content": m.content, "created_at": m.created_at.isoformat(), "read": bool(m.read_at)}
            for m in msgs
        ])
