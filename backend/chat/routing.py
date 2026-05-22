"""
WebSocket URL routing for the chat app.

Routes:
  ws://host/ws/chat/new/                → creates a new conversation, returns its ID
  ws://host/ws/chat/<conversation_id>/  → joins an existing conversation
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Join an existing conversation (UUID in URL)
    re_path(
        r"^ws/chat/(?P<conversation_id>[0-9a-f-]{36})/$",
        consumers.ChatConsumer.as_asgi(),
    ),
    # Create a new conversation on connect
    re_path(
        r"^ws/chat/new/$",
        consumers.ChatConsumer.as_asgi(),
    ),
]
