import uuid
from django.db import models
from django.conf import settings

class Conversation(models.Model):
    """
    Represents a single chat session between a user and the PM Bot agent.
    Each conversation maintains its own message history.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    # Auto-set to first user message content (truncated) on first message
    title = models.CharField(max_length=255, blank=True, default="New Conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        ordering = ["-updated_at"]
        db_table = "chatbot_conversation"

    def __str__(self):
        return f"[{self.user.username}] {self.title} ({self.id})"


class Message(models.Model):
    """
    A single message turn within a conversation.
    Stores user messages, assistant responses, and tool invocations.
    """

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("tool", "Tool"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    # Stores tool call metadata for assistant messages that invoked tools
    tool_calls = models.JSONField(null=True, blank=True)
    # Token usage for this message (from LLM response metadata)
    token_count = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["created_at"]
        db_table = "chatbot_message"

    def __str__(self):
        snippet = self.content[:60] + "..." if len(self.content) > 60 else self.content
        return f"[{self.role.upper()}] {snippet}"
