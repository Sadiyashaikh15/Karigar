"""Razorpay integration with a MOCK mode (used automatically when no keys are configured).

Flow (escrow style):
 1. customer pays after provider accepts  -> status PAID (money held by platform)
 2. provider completes the job            -> status RELEASED (payout = amount - commission)
 3. cancel after payment                  -> status REFUNDED
"""
import hashlib
import hmac
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from .models import Payment

MOCK_SIGNATURE = "mock_signature"


def is_mock_mode():
    return not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def _client():
    import razorpay
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def compute_signature(order_id, payment_id, secret=None):
    secret = secret or settings.RAZORPAY_KEY_SECRET
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def verify_payment_signature(order_id, payment_id, signature):
    if is_mock_mode():
        return hmac.compare_digest(signature or "", MOCK_SIGNATURE)
    expected = compute_signature(order_id, payment_id)
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(raw_body: bytes, signature: str):
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


@transaction.atomic
def create_order(booking):
    """Create (or reuse) the Razorpay order for an ACCEPTED booking."""
    existing = Payment.objects.filter(booking=booking).first()
    if existing and existing.status == Payment.Status.CREATED:
        return existing
    if existing:
        raise ValueError(f"Payment already {existing.status}")

    amount_paise = int(booking.amount * 100)
    if is_mock_mode():
        order_id, mock = f"order_mock_{uuid.uuid4().hex[:14]}", True
    else:
        order = _client().order.create(
            {"amount": amount_paise, "currency": "INR", "receipt": f"booking_{booking.id}",
             "notes": {"booking_id": str(booking.id)}}
        )
        order_id, mock = order["id"], False
    return Payment.objects.create(
        booking=booking, razorpay_order_id=order_id, amount=booking.amount,
        commission=booking.commission, provider_payout=booking.amount - booking.commission,
        is_mock=mock,
    )


@transaction.atomic
def mark_paid(order_id, payment_id):
    """Idempotent: safe to call from both the browser verify call AND the webhook."""
    payment = Payment.objects.select_for_update().select_related("booking").get(
        razorpay_order_id=order_id
    )
    if payment.status in (Payment.Status.PAID, Payment.Status.RELEASED):
        return payment, False
    if payment.status == Payment.Status.REFUNDED:
        return payment, False
    payment.razorpay_payment_id = payment_id
    payment.status = Payment.Status.PAID
    payment.save()
    booking = payment.booking
    if booking.status == "accepted":
        booking.status = "paid"
        booking.save(update_fields=["status", "updated_at"])
    return payment, True


def mark_failed(order_id):
    Payment.objects.filter(
        razorpay_order_id=order_id, status=Payment.Status.CREATED
    ).update(status=Payment.Status.FAILED)


def release_payout(booking):
    """Called when job is completed. In production: trigger Razorpay Route / payout here."""
    Payment.objects.filter(booking=booking, status=Payment.Status.PAID).update(
        status=Payment.Status.RELEASED
    )


def refund_payment(booking):
    payment = Payment.objects.filter(booking=booking, status=Payment.Status.PAID).first()
    if not payment:
        return None
    if not payment.is_mock and payment.razorpay_payment_id:
        try:
            _client().payment.refund(payment.razorpay_payment_id, {"amount": int(payment.amount * 100)})
        except Exception:  # keep going: mark for manual review rather than losing the cancel
            pass
    payment.status = Payment.Status.REFUNDED
    payment.save(update_fields=["status", "updated_at"])
    return payment
