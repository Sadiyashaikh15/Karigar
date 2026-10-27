import json

from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.users.permissions import IsCustomer

from . import services
from .models import Payment, WebhookEvent


class CreateOrderView(APIView):
    permission_classes = [IsCustomer]

    def post(self, request):
        try:
            booking = Booking.objects.get(pk=request.data.get("booking_id"), customer=request.user)
        except (Booking.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Booking not found"}, status=404)
        if booking.status != "accepted":
            return Response({"detail": "Booking must be accepted by the provider before payment."}, status=400)
        try:
            payment = services.create_order(booking)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        return Response({
            "order_id": payment.razorpay_order_id,
            "amount": int(payment.amount * 100),
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID or "mock",
            "mock": payment.is_mock,
            "booking_id": booking.id,
        })


class VerifyPaymentView(APIView):
    """Never trust the frontend: the signature is verified server-side."""
    permission_classes = [IsCustomer]

    def post(self, request):
        d = request.data
        order_id, pay_id, sig = d.get("razorpay_order_id"), d.get("razorpay_payment_id"), d.get("razorpay_signature")
        if not (order_id and pay_id):
            return Response({"detail": "Missing payment fields"}, status=400)
        try:
            payment = Payment.objects.select_related("booking").get(
                razorpay_order_id=order_id, booking__customer=request.user
            )
        except Payment.DoesNotExist:
            return Response({"detail": "Order not found"}, status=404)
        if not services.verify_payment_signature(order_id, pay_id, sig):
            return Response({"detail": "Invalid payment signature"}, status=400)
        try:
            with transaction.atomic():
                payment, changed = services.mark_paid(order_id, pay_id)
        except IntegrityError:
            return Response({"detail": "Payment id already used"}, status=400)
        return Response({"status": payment.status, "booking_status": payment.booking.status})


class WebhookView(APIView):
    """Razorpay -> server. Signature checked on the RAW body, events de-duplicated."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def post(self, request):
        raw = request.body
        if not services.verify_webhook_signature(raw, request.headers.get("X-Razorpay-Signature", "")):
            return Response({"detail": "Invalid signature"}, status=400)
        event_id = request.headers.get("X-Razorpay-Event-Id") or ""
        payload = json.loads(raw or b"{}")
        event = payload.get("event", "")
        if event_id:
            try:
                with transaction.atomic():
                    WebhookEvent.objects.create(event_id=event_id, event_type=event)
            except IntegrityError:
                return Response({"status": "duplicate-ignored"})
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id, pay_id = entity.get("order_id"), entity.get("id")
        try:
            if event in ("payment.captured", "order.paid") and order_id:
                services.mark_paid(order_id, pay_id)
            elif event == "payment.failed" and order_id:
                services.mark_failed(order_id)
        except Payment.DoesNotExist:
            pass
        return Response({"status": "ok"})


class PaymentStatusView(APIView):
    def get(self, request, booking_id):
        p = Payment.objects.filter(booking_id=booking_id).filter(
            booking__customer=request.user
        ).first() or Payment.objects.filter(
            booking_id=booking_id, booking__provider__user=request.user
        ).first()
        if not p:
            return Response({"detail": "No payment"}, status=404)
        return Response({"status": p.status, "amount": p.amount, "commission": p.commission,
                         "provider_payout": p.provider_payout})
