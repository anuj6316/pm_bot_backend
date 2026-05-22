"""LangGraph node implementations for issue analysis workflow."""

import logging
import os
from typing import Any

from langchain_community.chat_models import ChatLiteLLM
from langchain_core.messages import HumanMessage, SystemMessage

from .prompts import SYSTEM_PROMPTS

logger = logging.getLogger(__name__)

# Model config from environment (default to global standard)
MODEL_NAME = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")


def _get_llm() -> ChatLiteLLM:
    """Get a LangChain ChatLiteLLM instance for tracing.
    
    Returns:
        Configured ChatLiteLLM instance.
    """
    return ChatLiteLLM(
        model=MODEL_NAME,
        streaming=False,
    )


def analyze_issue(state: dict[str, Any]) -> dict[str, Any]:
    """Analyze the issue content to extract key information and sentiment.
    
    Args:
        state: Current workflow state containing issue_content.
        
    Returns:
        Updated state with analysis result.
    """
    issue_content = state.get("issue_content", "")
    logger.info("Node: Analyzing Issue...")

    model = _get_llm()
    messages = [
        SystemMessage(content=SYSTEM_PROMPTS["analyze"]),
        HumanMessage(content=issue_content),
    ]

    response = model.invoke(messages)
    analysis = response.content
    return {"analysis": str(analysis)}


def triage_issue(state: dict[str, Any]) -> dict[str, Any]:
    """Categorize the issue based on the analysis.
    
    Args:
        state: Current workflow state containing analysis.
        
    Returns:
        Updated state with category (BUG, FEATURE, or QUESTION).
    """
    analysis = state.get("analysis", "")
    logger.info("Node: Triaging Issue...")

    model = _get_llm()
    messages = [
        SystemMessage(content=SYSTEM_PROMPTS["triage"]),
        HumanMessage(content=f"Analysis: {analysis}"),
    ]

    response = model.invoke(messages)
    category = response.content.strip() if isinstance(response.content, str) else str(response.content).strip()
    return {"category": category}


def generate_response(state: dict[str, Any]) -> dict[str, Any]:
    """Draft the final response for the user.
    
    Args:
        state: Current workflow state containing issue_content and category.
        
    Returns:
        Updated state with draft_response.
    """
    issue_content = state.get("issue_content", "")
    category = state.get("category", "")
    logger.info("Node: Generating Response...")

    model = _get_llm()
    messages = [
        SystemMessage(content=SYSTEM_PROMPTS["generate"]),
        HumanMessage(content=f"Issue: {issue_content}\nCategory: {category}"),
    ]

    response = model.invoke(messages)
    draft_response = response.content
    return {"draft_response": str(draft_response)}
