from datetime import date, datetime, time, timedelta
from decimal import Decimal

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from apps.bookings import services
from apps.providers.models import Availability, Category, ProviderProfile, Service
from apps.users.models import User
from config.asgi import application


class ChatTests(TransactionTestCase):
    def setUp(self):
        cat = Category.objects.create(name="Tutor", slug="tutor")
        self.pu = User.objects.create_user("tp", "tp@x.com", "pass1234", role="provider")
        prof = ProviderProfile.objects.create(user=self.pu)
        svc = Service.objects.create(provider=prof, category=cat, title="Maths", price=Decimal("100"))
        for d in range(7):
            Availability.objects.create(provider=prof, day_of_week=d, start_time=time(9), end_time=time(17))
        self.cu = User.objects.create_user("cc", "cc@x.com", "pass1234", role="customer")
        self.other = User.objects.create_user("oo", "oo@x.com", "pass1234", role="customer")
        day = date.today() + timedelta(days=2)
        start = timezone.make_aware(datetime.combine(day, time(10)))
        self.booking = services.create_booking(self.cu, svc, start, "addr")

    def ws(self, user):
        tok = str(AccessToken.for_user(user))
        return WebsocketCommunicator(application, f"/ws/chat/{self.booking.id}/?token={tok}")

    async def test_chat_roundtrip_and_access_control(self):
        a, b, intruder = self.ws(self.cu), self.ws(self.pu), self.ws(self.other)
        self.assertTrue((await a.connect())[0])
        self.assertTrue((await b.connect())[0])
        self.assertFalse((await intruder.connect())[0])  # not a participant
        await a.send_json_to({"message": "Hello tutor"})
        got = await b.receive_json_from()
        # b may first receive a presence event
        while got["type"] != "message":
            got = await b.receive_json_from()
        self.assertEqual(got["content"], "Hello tutor")
        from apps.chat.models import Message
        self.assertEqual(await database_sync_to_async(Message.objects.count)(), 1)
        await a.disconnect()
        await b.disconnect()

    async def test_no_token_rejected(self):
        c = WebsocketCommunicator(application, f"/ws/chat/{self.booking.id}/")
        self.assertFalse((await c.connect())[0])
