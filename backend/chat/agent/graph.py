"""
LangGraph ReAct agent for the PM Bot chat.

Uses LangGraph's prebuilt create_react_agent with:
- ChatLiteLLM as the model (provider-agnostic via LLM_MODEL env var)
- PLANE_TOOLS as the tool set
- SYSTEM_PROMPT as the agent persona

The graph is NOT compiled as a module-level singleton here (unlike the triage
brain) — it's created fresh per-consumer to ensure clean state and allow
per-request configuration in the future.
"""

import os
import logging
from langchain_core.messages import SystemMessage
from langchain_community.chat_models import ChatLiteLLM
from langgraph.prebuilt import create_react_agent

from .tools import PLANE_TOOLS
from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Default model — overridable per-connection via WS query param
_DEFAULT_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")

# Allowlist of models the user can select from the UI.
# Key = identifier sent over WS, Value = LiteLLM model string.
ALLOWED_MODELS: dict[str, str] = {
    # Groq (fast, free tier)
    "groq/llama-3.3-70b-versatile": "groq/llama-3.3-70b-versatile",
    "groq/llama3-8b-8192": "groq/llama3-8b-8192",
    "groq/mixtral-8x7b-32768": "groq/mixtral-8x7b-32768",
    # OpenAI
    "openai/gpt-4o-mini": "openai/gpt-4o-mini",
    "openai/gpt-4o": "openai/gpt-4o",
    # Anthropic
    "anthropic/claude-3-5-haiku-20241022": "anthropic/claude-3-5-haiku-20241022",
    "anthropic/claude-3-5-sonnet-20241022": "anthropic/claude-3-5-sonnet-20241022",
    # Google
    "gemini/gemini-1.5-flash": "gemini/gemini-1.5-flash",
    "gemini/gemini-2.0-flash": "gemini/gemini-2.0-flash",
    # Ollama (local)
    "ollama/llama3.2": "ollama/llama3.2",
    "ollama/mistral": "ollama/mistral",
}


def create_chat_agent(model_name: str | None = None, user_id: int | None = None):
    """
    Build and return a compiled LangGraph ReAct agent.

    Args:
        model_name: Optional LiteLLM model string (e.g. 'groq/llama-3.3-70b-versatile').
                    Must be a key in ALLOWED_MODELS. Defaults to LLM_MODEL env var.
        user_id: Optional ID of the user to fetch custom API keys for.

    Returns:
        Compiled StateGraph compatible with .astream(stream_mode="messages").
    """
    # Validate and resolve model — default to env var if not in allowlist
    resolved_model = ALLOWED_MODELS.get(model_name or "", _DEFAULT_MODEL)
    if model_name and model_name not in ALLOWED_MODELS:
        logger.warning(
            f"Requested model '{model_name}' not in ALLOWED_MODELS, "
            f"falling back to default '{_DEFAULT_MODEL}'"
        )
        resolved_model = _DEFAULT_MODEL

    logger.info(f"Creating chat agent with model: {resolved_model}")

    extra_kwargs = {}
    if user_id:
        try:
            from authentication.models import UserAPIKey
            provider = resolved_model.split('/')[0].capitalize()
            if provider == 'Gemini': provider = 'Google' # Map gemini/ prefix to Google provider
            
            ukey = UserAPIKey.objects.filter(user_id=user_id, provider=provider).first()
            if ukey:
                logger.info(f"Using user-provided API key for {provider}")
                if provider == 'OpenAI': extra_kwargs['openai_api_key'] = ukey.api_key
                elif provider == 'Groq': extra_kwargs['groq_api_key'] = ukey.api_key
                elif provider == 'Anthropic': extra_kwargs['anthropic_api_key'] = ukey.api_key
                elif provider == 'Google': extra_kwargs['google_api_key'] = ukey.api_key
        except Exception as e:
            logger.error(f"Error fetching user API key: {e}")

    model = ChatLiteLLM(
        model=resolved_model,
        streaming=True,
        **extra_kwargs
    )

    # LangGraph ≥0.2 removed `state_modifier` — use `prompt` instead.
    agent = create_react_agent(
        model=model,
        tools=PLANE_TOOLS,
        prompt=SystemMessage(content=SYSTEM_PROMPT),
    )

    return agent

