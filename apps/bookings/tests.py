import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings import services
from apps.providers.models import Availability, Category, ProviderProfile, Service
from apps.users.models import User


def next_weekday_slot(hour=10):
    d = date.today() + timedelta(days=2)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d, timezone.make_aware(datetime.combine(d, time(hour, 0)))


class Base(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Plumber", slug="plumber")
        self.puser = User.objects.create_user("plumb", "p@x.com", "pass1234", role="provider",
                                              first_name="Pat")
        self.prof = ProviderProfile.objects.create(user=self.puser, latitude=18.52, longitude=73.85)
        self.svc = Service.objects.create(provider=self.prof, category=self.cat, title="Fix leak",
                                          price=Decimal("500"), duration_minutes=60)
        for d in range(7):
            Availability.objects.create(provider=self.prof, day_of_week=d,
                                        start_time=time(9), end_time=time(17))
        self.c1 = User.objects.create_user("c1", "c1@x.com", "pass1234", role="customer")
        self.c2 = User.objects.create_user("c2", "c2@x.com", "pass1234", role="customer")

    def client_for(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c


class AuthTests(TestCase):
    def test_register_login_and_roles(self):
        c = APIClient()
        r = c.post("/api/auth/register/", {"username": "bob", "email": "bob@x.com",
                                           "password": "secret123", "role": "provider"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(ProviderProfile.objects.filter(user__username="bob").exists())
        r = c.post("/api/auth/login/", {"username": "bob", "password": "secret123"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.json())
        self.assertEqual(r.json()["user"]["role"], "provider")

    def test_cannot_self_register_as_admin(self):
        r = APIClient().post("/api/auth/register/", {"username": "x", "email": "x@x.com",
                                                    "password": "secret123", "role": "admin"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_protected_endpoint_requires_token(self):
        self.assertEqual(APIClient().get("/api/bookings/").status_code, 401)


class SearchTests(Base):
    def test_near_me_filters_by_radius(self):
        c = APIClient()
        r = c.get("/api/providers/", {"lat": 18.52, "lng": 73.85, "radius": 5})
        self.assertEqual(r.json()["count"], 1)
        self.assertLess(r.json()["results"][0]["distance_km"], 1)
        r = c.get("/api/providers/", {"lat": 19.07, "lng": 72.87, "radius": 5})  # Mumbai
        self.assertEqual(r.json()["count"], 0)


class BookingTests(Base):
    def test_double_booking_prevented(self):
        _, start = next_weekday_slot()
        services.create_booking(self.c1, self.svc, start, "addr")
        with self.assertRaises(services.SlotUnavailable):
            services.create_booking(self.c2, self.svc, start, "addr")

    def test_overlapping_slot_blocked_and_free_slot_ok(self):
        d, start = next_weekday_slot(10)
        services.create_booking(self.c1, self.svc, start, "addr")
        slots = [s.hour for s in services.get_free_slots(self.prof, self.svc, d)]
        self.assertNotIn(10, slots)
        self.assertIn(11, slots)

    def test_api_returns_409_on_conflict(self):
        _, start = next_weekday_slot()
        body = {"service": self.svc.id, "start": start.isoformat(), "address": "x"}
        self.assertEqual(self.client_for(self.c1).post("/api/bookings/", body, format="json").status_code, 201)
        self.assertEqual(self.client_for(self.c2).post("/api/bookings/", body, format="json").status_code, 409)

    def test_provider_cannot_book_and_past_slot_rejected(self):
        _, start = next_weekday_slot()
        body = {"service": self.svc.id, "start": start.isoformat(), "address": "x"}
        self.assertEqual(self.client_for(self.puser).post("/api/bookings/", body, format="json").status_code, 403)
        past = timezone.now() - timedelta(days=1)
        body["start"] = past.isoformat()
        self.assertEqual(self.client_for(self.c1).post("/api/bookings/", body, format="json").status_code, 409)

    def test_full_lifecycle_payment_review(self):
        _, start = next_weekday_slot()
        cust, prov = self.client_for(self.c1), self.client_for(self.puser)
        b = cust.post("/api/bookings/", {"service": self.svc.id, "start": start.isoformat(),
                                         "address": "x"}, format="json").json()
        bid = b["id"]
        self.assertEqual(Decimal(b["commission"]), Decimal("50.00"))
        # cannot pay before acceptance
        self.assertEqual(cust.post("/api/payments/create-order/", {"booking_id": bid}, format="json").status_code, 400)
        # customer cannot accept their own booking
        self.assertEqual(cust.post(f"/api/bookings/{bid}/accept/").status_code, 403)
        self.assertEqual(prov.post(f"/api/bookings/{bid}/accept/").status_code, 200)
        order = cust.post("/api/payments/create-order/", {"booking_id": bid}, format="json").json()
        self.assertTrue(order["mock"])
        # wrong signature rejected
        bad = cust.post("/api/payments/verify/", {"razorpay_order_id": order["order_id"],
                                                  "razorpay_payment_id": "pay_1", "razorpay_signature": "nope"},
                        format="json")
        self.assertEqual(bad.status_code, 400)
        ok = cust.post("/api/payments/verify/", {"razorpay_order_id": order["order_id"],
                                                 "razorpay_payment_id": "pay_1",
                                                 "razorpay_signature": "mock_signature"}, format="json")
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.json()["booking_status"], "paid")
        # idempotent re-verify
        self.assertEqual(cust.post("/api/payments/verify/", {"razorpay_order_id": order["order_id"],
                                                             "razorpay_payment_id": "pay_1",
                                                             "razorpay_signature": "mock_signature"},
                                   format="json").status_code, 200)
        # review not allowed before completion
        rv = {"booking": bid, "rating": 5, "comment": "great"}
        self.assertEqual(cust.post("/api/reviews/", rv, format="json").status_code, 400)
        self.assertEqual(prov.post(f"/api/bookings/{bid}/start/").status_code, 200)
        self.assertEqual(prov.post(f"/api/bookings/{bid}/complete/").status_code, 200)
        self.assertEqual(cust.get(f"/api/payments/status/{bid}/").json()["status"], "released")
        self.assertEqual(cust.post("/api/reviews/", rv, format="json").status_code, 201)
        self.assertEqual(cust.post("/api/reviews/", rv, format="json").status_code, 400)  # one per booking
        self.prof.refresh_from_db()
        self.assertEqual(self.prof.avg_rating, 5)
        self.assertEqual(self.prof.completed_jobs, 1)

    def test_profanity_blocked(self):
        _, start = next_weekday_slot()
        b = services.create_booking(self.c1, self.svc, start, "x")
        b.status = "completed"
        b.save()
        r = self.client_for(self.c1).post("/api/reviews/", {"booking": b.id, "rating": 1, "comment": "you shit"},
                                          format="json")
        self.assertEqual(r.status_code, 400)

    def test_cancel_paid_booking_refunds(self):
        _, start = next_weekday_slot()
        cust, prov = self.client_for(self.c1), self.client_for(self.puser)
        bid = cust.post("/api/bookings/", {"service": self.svc.id, "start": start.isoformat(),
                                           "address": "x"}, format="json").json()["id"]
        prov.post(f"/api/bookings/{bid}/accept/")
        o = cust.post("/api/payments/create-order/", {"booking_id": bid}, format="json").json()
        cust.post("/api/payments/verify/", {"razorpay_order_id": o["order_id"], "razorpay_payment_id": "p2",
                                            "razorpay_signature": "mock_signature"}, format="json")
        self.assertEqual(cust.post(f"/api/bookings/{bid}/cancel/").status_code, 200)
        self.assertEqual(cust.get(f"/api/payments/status/{bid}/").json()["status"], "refunded")
        # slot is free again
        self.assertEqual(self.client_for(self.c2).post(
            "/api/bookings/", {"service": self.svc.id, "start": start.isoformat(), "address": "y"},
            format="json").status_code, 201)

    def test_expire_unpaid(self):
        _, start = next_weekday_slot()
        b = services.create_booking(self.c1, self.svc, start, "x")
        services.accept(b.id, self.puser)
        from apps.bookings.models import Booking
        Booking.objects.filter(pk=b.pk).update(accepted_at=timezone.now() - timedelta(minutes=30))
        self.assertEqual(services.expire_stale_bookings(), 1)
        b.refresh_from_db()
        self.assertEqual(b.status, "cancelled")


@override_settings(RAZORPAY_KEY_ID="k", RAZORPAY_KEY_SECRET="s", RAZORPAY_WEBHOOK_SECRET="whsec")
class WebhookTests(Base):
    def test_webhook_signature_and_idempotency(self):
        import hashlib, hmac
        from apps.payments.models import Payment
        _, start = next_weekday_slot()
        b = services.create_booking(self.c1, self.svc, start, "x")
        services.accept(b.id, self.puser)
        Payment.objects.create(booking=b, razorpay_order_id="order_X", amount=b.amount)
        body = json.dumps({"event": "payment.captured",
                           "payload": {"payment": {"entity": {"id": "pay_X", "order_id": "order_X"}}}}).encode()
        sig = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
        c = APIClient()
        bad = c.post("/api/payments/webhook/", data=body, content_type="application/json",
                     HTTP_X_RAZORPAY_SIGNATURE="bad", HTTP_X_RAZORPAY_EVENT_ID="e1")
        self.assertEqual(bad.status_code, 400)
        for expected in ("ok", "duplicate-ignored"):
            r = c.post("/api/payments/webhook/", data=body, content_type="application/json",
                       HTTP_X_RAZORPAY_SIGNATURE=sig, HTTP_X_RAZORPAY_EVENT_ID="e1")
            self.assertEqual(r.json()["status"], expected)
        b.refresh_from_db()
        self.assertEqual(b.status, "paid")
