"""LangGraph reasoning workflow for PM Bot issue analysis."""

import logging
import os
from typing import Any, TypedDict

import mlflow
from langgraph.graph import END, StateGraph

from .nodes import analyze_issue, generate_response, triage_issue

logger = logging.getLogger(__name__)

# Enable MLflow tracing for LangChain/LangGraph if Databricks is configured
try:
    if os.getenv("DATABRICKS_HOST"):
        mlflow.langchain.autolog()
        logger.info("Databricks MLflow autologging activated for LangGraph.")
except Exception as e:
    logger.warning(f"Could not activate MLflow autologging: {e}")


class AgentState(TypedDict):
    """State stored throughout the LangGraph workflow.
    
    Attributes:
        issue_content: The original issue content to process.
        analysis: Extracted key information and sentiment from analysis.
        category: Triage category (BUG, FEATURE, QUESTION).
        draft_response: Generated response draft.
        error: Error message if any step fails.
    """

    issue_content: str
    analysis: str
    category: str
    draft_response: str
    error: str


def create_agent_graph() -> StateGraph:
    """Create and compile the LangGraph reasoning workflow.
    
    Returns:
        Compiled StateGraph representing the agent workflow.
    """
    # 1. Initialize the Graph
    workflow = StateGraph(AgentState)

    # 2. Add Nodes
    workflow.add_node("analyze", analyze_issue)
    workflow.add_node("triage", triage_issue)
    workflow.add_node("generate", generate_response)

    # 3. Define Edges (Sequential flow)
    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "triage")
    workflow.add_edge("triage", "generate")
    workflow.add_edge("generate", END)

    # 4. Compile
    return workflow.compile()


# Singleton instance of the graph
brain_graph = create_agent_graph()


def run_brain(issue_content: str) -> dict[str, Any]:
    """Execute the brain workflow for a given issue.
    
    Args:
        issue_content: The issue content to process.
        
    Returns:
        Dictionary containing workflow results with keys:
        - issue_content, analysis, category, draft_response, error
    """
    initial_state = {
        "issue_content": issue_content,
        "analysis": "",
        "category": "",
        "draft_response": "",
        "error": "",
    }

    try:
        final_state = brain_graph.invoke(initial_state)
        return final_state
    except Exception as e:
        logger.error(f"Error executing LangGraph: {str(e)}")
        return {**initial_state, "error": str(e)}
