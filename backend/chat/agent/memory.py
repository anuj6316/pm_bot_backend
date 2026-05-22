"""
Conversation memory backed by the chat Message model.

Provides async helpers to load a conversation's history as LangChain
BaseMessage objects and to persist new messages after the agent responds.
"""

import logging
from typing import Union
from channels.db import database_sync_to_async
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    BaseMessage,
)

logger = logging.getLogger(__name__)

# Maximum number of past messages to load as context (keeps token count bounded)
MAX_HISTORY_MESSAGES = 40


@database_sync_to_async
def load_history(conversation_id) -> list[BaseMessage]:
    """
    Load the conversation history from the database and return it as a
    list of LangChain BaseMessage objects suitable for passing to the agent.

    Only the most recent MAX_HISTORY_MESSAGES messages are loaded to prevent
    context window overflow.
    """
    from chat.models import Message  # local import avoids circular deps at module load

    messages_qs = (
        Message.objects.filter(conversation_id=conversation_id)
        .order_by("-created_at")[:MAX_HISTORY_MESSAGES]
    )
    # Reverse so oldest is first (chronological order for the model)
    db_messages = list(reversed(list(messages_qs)))

    history: list[BaseMessage] = []
    for msg in db_messages:
        if msg.role == "user":
            history.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            history.append(AIMessage(content=msg.content))
        elif msg.role == "tool":
            history.append(ToolMessage(content=msg.content, tool_call_id=""))
    return history


@database_sync_to_async
def save_message(
    conversation_id,
    role: str,
    content: str,
    tool_calls: Union[list, None] = None,
) -> None:
    """
    Persist a single message to the database.

    Args:
        conversation_id: UUID of the parent Conversation.
        role: 'user', 'assistant', or 'tool'.
        content: The text content of the message.
        tool_calls: Optional list of tool call dicts (for assistant messages).
    """
    from chat.models import Message, Conversation  # local import

    try:
        Message.objects.create(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        )
        # Update conversation's updated_at timestamp by simply saving or update()
        # To touch without loading, we can use an empty update with a Dummy change 
        # but in Django 6.0 standard behavior is usually sufficient.
        Conversation.objects.filter(id=conversation_id).update(title=Conversation.objects.get(id=conversation_id).title)
    except Exception as e:
        logger.error(f"Failed to save message for conversation {conversation_id}: {e}")


@database_sync_to_async
def set_conversation_title(conversation_id, title: str) -> None:
    """
    Set the auto-generated title of a conversation (from first user message).
    Only updates if the title is still the default 'New Conversation'.
    """
    from chat.models import Conversation  # local import

    Conversation.objects.filter(
        id=conversation_id, title="New Conversation"
    ).update(title=title[:120])  # truncate to fit CharField max_length
