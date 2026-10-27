from django.urls import path

from .consumers import ChatConsumer

websocket_urlpatterns = [
    path("ws/chat/<int:booking_id>/", ChatConsumer.as_asgi()),
]
