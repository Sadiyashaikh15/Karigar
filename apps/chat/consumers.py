from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.bookings.models import Booking

from .models import Message

User = get_user_model()


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """ws://host/ws/chat/<booking_id>/?token=<JWT access token>

    Client -> server: {"message": "hi"} | {"typing": true} | {"read": true}
    Server -> client: {"type": "message"|"typing"|"read"|"presence", ...}
    """

    async def connect(self):
        self.booking_id = self.scope["url_route"]["kwargs"]["booking_id"]
        self.user = await self._auth()
        if not self.user or not await self._is_participant():
            await self.close(code=4403)
            return
        self.group = f"chat_{self.booking_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.channel_layer.group_send(
            self.group, {"type": "chat.presence", "user": self.user.id, "online": True}
        )

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_send(
                self.group, {"type": "chat.presence", "user": self.user.id, "online": False}
            )
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("message"):
            text = str(content["message"]).strip()[:2000]
            if not text:
                return
            msg = await self._save(text)
            await self.channel_layer.group_send(self.group, {"type": "chat.message", **msg})
        elif "typing" in content:
            await self.channel_layer.group_send(
                self.group, {"type": "chat.typing", "user": self.user.id, "typing": bool(content["typing"])}
            )
        elif content.get("read"):
            await self._mark_read()
            await self.channel_layer.group_send(self.group, {"type": "chat.read", "user": self.user.id})

    # ---- group event handlers ----
    async def chat_message(self, e):
        await self.send_json({"type": "message", **{k: v for k, v in e.items() if k != "type"}})

    async def chat_typing(self, e):
        if e["user"] != self.user.id:
            await self.send_json({"type": "typing", "user": e["user"], "typing": e["typing"]})

    async def chat_read(self, e):
        if e["user"] != self.user.id:
            await self.send_json({"type": "read", "user": e["user"]})

    async def chat_presence(self, e):
        if e["user"] != self.user.id:
            await self.send_json({"type": "presence", "user": e["user"], "online": e["online"]})

    # ---- db helpers ----
    @database_sync_to_async
    def _auth(self):
        from rest_framework_simplejwt.tokens import AccessToken

        token = parse_qs(self.scope["query_string"].decode()).get("token", [None])[0]
        if not token:
            return None
        try:
            return User.objects.get(pk=AccessToken(token)["user_id"], is_active=True)
        except Exception:
            return None

    @database_sync_to_async
    def _is_participant(self):
        return Booking.objects.filter(pk=self.booking_id).filter(
            customer=self.user
        ).exists() or Booking.objects.filter(pk=self.booking_id, provider__user=self.user).exists()

    @database_sync_to_async
    def _save(self, text):
        m = Message.objects.create(booking_id=self.booking_id, sender=self.user, content=text)
        return {"id": m.id, "sender": self.user.id, "sender_name": self.user.get_full_name() or self.user.username,
                "content": m.content, "created_at": m.created_at.isoformat()}

    @database_sync_to_async
    def _mark_read(self):
        Message.objects.filter(booking_id=self.booking_id, read_at__isnull=True).exclude(
            sender=self.user
        ).update(read_at=timezone.now())
