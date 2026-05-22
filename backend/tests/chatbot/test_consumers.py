"""
Integration tests for the ChatConsumer WebSocket endpoint.

Uses channels.testing.WebsocketCommunicator for in-process WS testing —
no live server required. The agent itself is mocked so LLM calls are skipped.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


def _build_ws_url(path: str, token: str) -> str:
    return f"{path}?token={token}"


@database_sync_to_async
def _get_token_for(user) -> str:
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


class ChatConsumerAuthTest(TransactionTestCase):
    """Tests for WebSocket authentication behaviour."""

    def setUp(self):
        from backend.asgi import application
        self.application = application

    async def test_unauthenticated_connection_rejected(self):
        """Connection without a token must be closed with code 4001."""
        communicator = WebsocketCommunicator(
            self.application, "/ws/chat/new/"
        )
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4001)

    async def test_invalid_token_rejected(self):
        """Connection with a malformed JWT must be rejected."""
        communicator = WebsocketCommunicator(
            self.application, "/ws/chat/new/?token=not.a.valid.token"
        )
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4001)

    async def test_authenticated_connection_accepted(self):
        """Valid JWT results in a successful connection + 'connected' event."""
        user = await database_sync_to_async(User.objects.create_user)(
            username="wsuser", password="pass123"
        )
        token = await _get_token_for(user)

        communicator = WebsocketCommunicator(
            self.application, f"/ws/chat/new/?token={token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Should receive the 'connected' acknowledgement
        raw = await communicator.receive_json_from()
        self.assertEqual(raw["type"], "connected")
        self.assertIn("conversation_id", raw["data"])

        await communicator.disconnect()


class ChatConsumerMessageTest(TransactionTestCase):
    """Tests for message sending and streaming behaviour."""

    def setUp(self):
        from backend.asgi import application
        self.application = application

    @patch("chat.consumers.create_chat_agent")
    async def test_message_triggers_streaming_response(self, mock_create_agent):
        """Sending a message should produce token events followed by 'done'."""
        # Set up mock agent that yields a single AIMessageChunk
        from langchain_core.messages import AIMessageChunk

        async def mock_astream(*args, **kwargs):
            chunk = AIMessageChunk(content="Hello! ")
            yield chunk, {}
            chunk2 = AIMessageChunk(content="How can I help?")
            yield chunk2, {}

        mock_agent = MagicMock()
        mock_agent.astream = mock_astream
        mock_create_agent.return_value = mock_agent

        user = await database_sync_to_async(User.objects.create_user)(
            username="streamuser", password="pass123"
        )
        token = await _get_token_for(user)

        communicator = WebsocketCommunicator(
            self.application, f"/ws/chat/new/?token={token}"
        )
        await communicator.connect()
        await communicator.receive_json_from()  # consume 'connected' event

        # Send a user message
        await communicator.send_json_to({
            "type": "message",
            "content": "Show me open issues",
        })

        # Collect events until 'done'
        events = []
        for _ in range(10):
            data = await communicator.receive_json_from(timeout=5)
            events.append(data)
            if data["type"] == "done":
                break

        types = [e["type"] for e in events]
        self.assertIn("token", types)
        self.assertIn("done", types)
        self.assertNotIn("error", types)

        await communicator.disconnect()

    async def test_oversized_message_returns_error(self):
        """Messages exceeding CHATBOT_MAX_MESSAGE_LENGTH return an error event."""
        user = await database_sync_to_async(User.objects.create_user)(
            username="bigmsguser", password="pass123"
        )
        token = await _get_token_for(user)

        communicator = WebsocketCommunicator(
            self.application, f"/ws/chat/new/?token={token}"
        )
        await communicator.connect()
        await communicator.receive_json_from()  # consume 'connected'

        await communicator.send_json_to({
            "type": "message",
            "content": "x" * 5000,  # exceeds default 4096 limit
        })

        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response["type"], "error")
        self.assertIn("too long", response["data"])

        await communicator.disconnect()


class ChatbotRESTAPITest(TestCase):
    """Tests for the REST API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="restuser", password="pass123"
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {self.token}"

    def test_list_conversations_empty(self):
        response = self.client.get("/api/v1/chat/conversations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_create_conversation(self):
        response = self.client.post("/api/v1/chat/conversations/", {}, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["title"], "New Conversation")

    def test_retrieve_conversation(self):
        from chat.models import Conversation
        conv = Conversation.objects.create(user=self.user, title="My Chat")
        response = self.client.get(f"/api/v1/chat/conversations/{conv.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "My Chat")

    def test_delete_conversation(self):
        from chat.models import Conversation
        conv = Conversation.objects.create(user=self.user)
        response = self.client.delete(f"/api/v1/chat/conversations/{conv.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Conversation.objects.filter(id=conv.id).exists())

    def test_list_conversations_unauthenticated(self):
        self.client.defaults.pop("HTTP_AUTHORIZATION", None)
        response = self.client.get("/api/v1/chat/conversations/")
        self.assertEqual(response.status_code, 401)

    def test_cannot_access_other_users_conversation(self):
        other_user = User.objects.create_user(username="other", password="pass")
        from chat.models import Conversation
        conv = Conversation.objects.create(user=other_user, title="Private")
        response = self.client.get(f"/api/v1/chat/conversations/{conv.id}/")
        self.assertEqual(response.status_code, 404)
