"""
QueryOrchestrator LangGraph agent.
Specialized for single-turn system queries using DB + Plane tools.
"""

import os
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.chat_models import ChatLiteLLM
from langgraph.prebuilt import create_react_agent

from .tools import PLANE_TOOLS
from .db_tools import DB_TOOLS
from .prompts import QUERY_SYSTEM_PROMPT
from .graph import ALLOWED_MODELS

logger = logging.getLogger(__name__)

# Combine tools
ALL_QUERY_TOOLS = DB_TOOLS + PLANE_TOOLS

def create_query_orchestrator(model_name: str | None = None, user_id: int | None = None):
    """
    Build and return a compiled LangGraph ReAct agent for system queries.
    """
    default_model = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    resolved_model = ALLOWED_MODELS.get(model_name or "", default_model)

    logger.info(f"Creating query orchestrator with model: {resolved_model}")

    extra_kwargs = {}
    if user_id:
        try:
            from authentication.models import UserAPIKey
            provider = resolved_model.split('/')[0].capitalize()
            if provider == 'Gemini': provider = 'Google'
            
            ukey = UserAPIKey.objects.filter(user_id=user_id, provider=provider).first()
            if ukey:
                logger.info(f"Using user-provided API key for {provider} (query)")
                if provider == 'OpenAI': extra_kwargs['openai_api_key'] = ukey.api_key
                elif provider == 'Groq': extra_kwargs['groq_api_key'] = ukey.api_key
                elif provider == 'Anthropic': extra_kwargs['anthropic_api_key'] = ukey.api_key
                elif provider == 'Google': extra_kwargs['google_api_key'] = ukey.api_key
        except Exception as e:
            logger.error(f"Error fetching user API key for query: {e}")

    model = ChatLiteLLM(
        model=resolved_model,
        streaming=False, # Single-turn query typically doesn't need streaming here
        **extra_kwargs
    )

    agent = create_react_agent(
        model=model,
        tools=ALL_QUERY_TOOLS,
        prompt=SystemMessage(content=QUERY_SYSTEM_PROMPT),
    )

    return agent

def run_query(query: str, user_id: int, user_role: str, allowed_projects: list, model_name: str = None):
    """
    Synchronous helper to run the query orchestrator.
    """
    orchestrator = create_query_orchestrator(model_name, user_id=user_id)
    
    # Configure tool access via the config dict
    config = {
        "configurable": {
            "user_id": user_id,
            "role": user_role,
            "allowed_projects": allowed_projects,
            "is_superuser": user_role == 'admin' # Simple proxy for this demo
        }
    }
    
    try:
        inputs = {"messages": [HumanMessage(content=query)]}
        result = orchestrator.invoke(inputs, config=config)
        
        # Extract the last message content (the answer)
        if "messages" in result and result["messages"]:
            return result["messages"][-1].content
        return "No response generated."
        
    except Exception as e:
        logger.error(f"QueryOrchestrator error: {e}")
        return f"Error processing query: {str(e)}"
