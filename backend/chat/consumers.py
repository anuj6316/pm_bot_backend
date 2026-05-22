"""
ChatConsumer — WebSocket handler for the PM Bot conversational agent.

## Connection lifecycle
1. Middleware validates JWT and injects scope["user"] before connect() runs.
2. connect() rejects unauthenticated users (close code 4001).
3. receive() validates message, enforces rate limiting, runs the LangGraph agent.
4. Agent responses are streamed token-by-token back to the client.
5. All messages (user + assistant) are persisted to the DB after each turn.

## Rate limiting
Per-user rate limiting is enforced via an in-memory sliding window counter
backed by the channel layer's Redis connection. Exceeding CHATBOT_RATE_LIMIT
messages per minute closes the connection with a clear error message.
"""

import asyncio
import json
import logging
import time
from collections import deque

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage

from .agent.graph import create_chat_agent, ALLOWED_MODELS, _DEFAULT_MODEL
from .agent.memory import load_history, save_message, set_conversation_title

logger = logging.getLogger(__name__)

# Close codes
WS_CLOSE_UNAUTHORIZED = 4001
WS_CLOSE_NOT_FOUND = 4004
WS_CLOSE_RATE_LIMITED = 4029


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Async WebSocket consumer for real-time chat interaction.

    Streams LangGraph agent responses token-by-token to the connected client.
    """

    # In-memory per-user rate limit tracker: user_id → deque of timestamps
    _rate_trackers: dict = {}

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self):
        user = self.scope.get("user")

        if not user or isinstance(user, AnonymousUser):
            logger.warning("Unauthenticated WebSocket connection attempt rejected.")
            await self.close(code=WS_CLOSE_UNAUTHORIZED)
            return

        self.user = user
        self.rate_tracker = self._get_rate_tracker(user.id)

        # Parse optional model query param (e.g. ?token=...&model=groq/llama-3.3-70b-versatile)
        query_string = self.scope.get("query_string", b"").decode()
        qs_params = dict(
            part.split("=", 1) for part in query_string.split("&") if "=" in part
        )
        requested_model = qs_params.get("model", "").strip()
        self.active_model = (
            requested_model if requested_model in ALLOWED_MODELS else _DEFAULT_MODEL
        )
        self.agent = create_chat_agent(self.active_model, user_id=user.id)

        # Resolve or create conversation
        conversation_id = self.scope["url_route"]["kwargs"].get("conversation_id")
        if conversation_id:
            self.conversation = await self._get_conversation(str(conversation_id))
            if not self.conversation:
                await self.close(code=WS_CLOSE_NOT_FOUND)
                return
        else:
            self.conversation = await self._create_conversation()

        await self.accept()
        logger.info(
            f"WS connected: user={user.id}, conversation={self.conversation.id}"
        )

        # Send connection acknowledgement with conversation metadata
        await self.send(json.dumps({
            "type": "connected",
            "data": {
                "conversation_id": str(self.conversation.id),
                "title": self.conversation.title,
                "model": self.active_model,
            },
        }))

    async def disconnect(self, close_code):
        logger.info(
            f"WS disconnected: user={getattr(self, 'user', '?')}, "
            f"code={close_code}"
        )

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def receive(self, text_data=None, bytes_data=None):
        # Parse incoming message
        try:
            payload = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            await self._send_error("Invalid JSON payload.")
            return

        if payload.get("type") != "message":
            return  # Silently ignore unrecognised message types

        content = payload.get("content", "").strip()
        if not content:
            return

        # Enforce message size limit
        max_len = getattr(settings, "CHATBOT_MAX_MESSAGE_LENGTH", 4096)
        if len(content) > max_len:
            await self._send_error(f"Message too long (max {max_len} characters).")
            return

        # Enforce rate limit
        if not self._check_rate_limit():
            await self._send_error(
                f"Rate limit exceeded — max {getattr(settings, 'CHATBOT_RATE_LIMIT', 20)} "
                f"messages per minute. Please wait before sending another message."
            )
            return

        # Persist user message
        await save_message(self.conversation.id, "user", content)

        # Auto-set conversation title from first user message
        await set_conversation_title(self.conversation.id, content[:80])

        # Run agent and stream response
        await self._run_agent(content)

    # ------------------------------------------------------------------
    # Agent execution with streaming
    # ------------------------------------------------------------------

    async def _run_agent(self, user_message: str):
        """
        Run the LangGraph ReAct agent and stream its response back to the client.

        Handles:
        - Token-by-token AI response streaming
        - Tool call notifications
        - Tool result notifications
        - Timeout enforcement
        - Error recovery
        """
        # Load history and append current user message
        history = await load_history(self.conversation.id)
        input_messages = history + [HumanMessage(content=user_message)]

        full_response = ""
        tool_calls_log = []
        timeout = getattr(settings, "CHATBOT_AGENT_TIMEOUT", 120)

        try:
            async with asyncio.timeout(timeout):
                # Prepare runtime configuration for tools and persona
                role = getattr(self.user, "role", "developer")
                config = {
                    "configurable": {
                        "allowed_projects": self.user.get_allowed_projects(),
                        "is_superuser": self.user.is_superuser,
                        "role": role,
                    }
                }

                # Persona augmentation: Tell the agent its role and constraints
                role_instruction = f"\n\n[SECURITY CONTEXT]: Your current user is logged in as a {role.upper()}."
                if role == "consultant":
                    role_instruction += " You have global read-access but are STICTLY READ-ONLY for Plane operations (no creating/updating issues)."
                elif role == "developer":
                    role_instruction += " You can only read/write to specific authorized projects."
                
                # Prepend the role instruction to the conversation context
                input_messages = [SystemMessage(content=role_instruction)] + input_messages

                async for chunk, metadata in self.agent.astream(
                    {"messages": input_messages},
                    config=config,
                    stream_mode="messages",
                ):
                    # --- AI token streaming ---
                    if isinstance(chunk, AIMessageChunk) and chunk.content:
                        if isinstance(chunk.content, str):
                            full_response += chunk.content
                            await self.send(json.dumps({
                                "type": "token",
                                "data": chunk.content,
                            }))

                    # --- Tool call notification (mid-stream) ---
                    if (
                        hasattr(chunk, "tool_calls")
                        and chunk.tool_calls
                        and getattr(chunk, "invalid_tool_calls", None) is None
                    ):
                        for tc in chunk.tool_calls:
                            if tc.get("name"):  # ignore streaming fragments
                                tool_calls_log.append(tc)
                                await self.send(json.dumps({
                                    "type": "tool_call",
                                    "data": {
                                        "name": tc.get("name", ""),
                                        "args": tc.get("args", {}),
                                    },
                                }))

                    # --- Tool result (from ToolMessage nodes) ---
                    if (
                        hasattr(chunk, "type")
                        and chunk.type == "tool"
                        and chunk.content
                    ):
                        await self.send(json.dumps({
                            "type": "tool_result",
                            "data": str(chunk.content)[:1000],  # cap for WS payload size
                        }))

        except asyncio.TimeoutError:
            logger.warning(
                f"Agent timeout for conversation {self.conversation.id} "
                f"after {timeout}s"
            )
            await self._send_error(
                "The agent took too long to respond. Please try again with a simpler request."
            )
            return

        except Exception as e:
            logger.error(
                f"Agent error for conversation {self.conversation.id}: {e}",
                exc_info=True,
            )
            await self._send_error(
                "An unexpected error occurred while processing your request."
            )
            return

        # Signal stream completion
        await self.send(json.dumps({"type": "done", "data": ""}))

        # Persist the assistant's full response
        if full_response:
            await save_message(
                self.conversation.id,
                "assistant",
                full_response,
                tool_calls=tool_calls_log if tool_calls_log else None,
            )

    # ------------------------------------------------------------------
    # Rate limiting (sliding window, in-memory)
    # ------------------------------------------------------------------

    def _get_rate_tracker(self, user_id) -> deque:
        """Return (or create) the per-user sliding window deque."""
        if user_id not in ChatConsumer._rate_trackers:
            ChatConsumer._rate_trackers[user_id] = deque()
        return ChatConsumer._rate_trackers[user_id]

    def _check_rate_limit(self) -> bool:
        """
        Sliding window rate limiter.
        Returns True if the request is allowed, False if the limit is exceeded.
        """
        limit = getattr(settings, "CHATBOT_RATE_LIMIT", 20)
        now = time.monotonic()
        window = 60.0  # 1 minute

        # Remove timestamps outside the window
        while self.rate_tracker and self.rate_tracker[0] < now - window:
            self.rate_tracker.popleft()

        if len(self.rate_tracker) >= limit:
            return False

        self.rate_tracker.append(now)
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _send_error(self, message: str):
        """Send a typed error event to the client."""
        await self.send(json.dumps({"type": "error", "data": message}))

    @database_sync_to_async
    def _get_conversation(self, conversation_id: str):
        """Fetch a Conversation belonging to the current user."""
        from chat.models import Conversation
        try:
            return Conversation.objects.get(id=conversation_id, user=self.user)
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def _create_conversation(self):
        """Create a new Conversation for the current user."""
        from chat.models import Conversation
        return Conversation.objects.create(user=self.user)
