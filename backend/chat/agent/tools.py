"""
Plane tools for the PM Bot conversational agent.

Each function is decorated with @tool (LangChain) so the LangGraph ReAct agent
can discover, call, and interpret them automatically.

All tools instantiate PlaneClient internally — they do NOT share state —
so they remain safe for concurrent async use.
"""

import logging

from integrations.plane.client import PlaneClient
from integrations.plane.exceptions import PlaneAPIError, PlaneNotFoundError
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _client() -> PlaneClient:
    """Factory that returns a fresh PlaneClient instance."""
    return PlaneClient()


# ---------------------------------------------------------------------------
# READ tools
# ---------------------------------------------------------------------------


@tool
def list_projects(config: RunnableConfig) -> str:
    """
    List authorized projects.
    """
    conf = config.get("configurable", {})
    user_role = conf.get("role", "developer")
    allowed_ids = conf.get("allowed_projects", [])
    is_superuser = conf.get("is_superuser", False)

    try:
        data = _client().list_projects()
        all_projects = data.get("results", []) if isinstance(data, dict) else data

        # Admin / Consultant / Superuser see everything
        is_global = is_superuser or user_role in ["admin", "consultant"]

        projects = [p for p in all_projects if is_global or p.get("id") in allowed_ids]

        if not projects:
            return "No projects found."

        lines = [f"- **{p['name']}** (ID: `{p['id']}`)" for p in projects]
        return f"Found {len(projects)} authorized project(s):\n" + "\n".join(lines)
    except PlaneAPIError as e:
        logger.error(f"list_projects tool error: {e}")
        return f"Error fetching projects: {e.message}"


def validate_project_access(
    project_id: str, config: RunnableConfig, write: bool = False
) -> str | None:
    """
    Validates if the user has permission to access (and potentially write to) a project.
    Returns: None if authorized, or an error message string if denied.
    """
    conf = config.get("configurable", {})
    user_role = conf.get("role", "developer")
    is_superuser = conf.get("is_superuser", False)
    allowed_ids = conf.get("allowed_projects", [])

    # Global roles (Admin/Superuser/Consultant) bypass visibility check
    is_global = is_superuser or user_role in ["admin", "consultant"]

    # 1. Visibility Check
    if not is_global:
        if project_id and project_id not in allowed_ids:
            return f"⚠️ ACCESS DENIED: You are only authorized for projects: {', '.join(allowed_ids)}"

    # 2. Write Check
    if write:
        if user_role == "consultant":
            return "⚠️ READ-ONLY: As a Consultant, you can view data but are not authorized to create or modify issues."

        # Developer must have visibility to write
        if user_role == "developer" and project_id and project_id not in allowed_ids:
            return (
                f"⚠️ ACCESS DENIED: Cannot write to unauthorized project `{project_id}`."
            )

    return None


@tool
def list_issues(project_id: str, config: RunnableConfig) -> str:
    """
    List issues in a project.
    """
    error = validate_project_access(project_id, config, write=False)
    if error:
        return error

    try:
        data = _client().list_issues(project_id)
        issues = data.get("results", []) if isinstance(data, dict) else data
        if not issues:
            return f"No issues found in project `{project_id}`."
        lines = []
        for issue in issues:
            priority = issue.get("priority", "none")
            state = (
                issue.get("state_detail", {}).get("name", "Unknown")
                if issue.get("state_detail")
                else "Unknown"
            )
            lines.append(
                f"- **{issue.get('name', 'Untitled')}** | ID: `{issue.get('id')}` | "
                f"Priority: {priority} | State: {state}"
            )
        return f"Found {len(issues)} issue(s) in project `{project_id}`:\n" + "\n".join(
            lines
        )
    except PlaneAPIError as e:
        logger.error(f"list_issues tool error: {e}")
        return f"Error fetching issues for project `{project_id}`: {e.message}"


@tool
def get_issue(project_id: str, issue_id: str, config: RunnableConfig) -> str:
    """
    Get issue details. Directly fetches a specific issue by ID.
    """
    error = validate_project_access(project_id, config, write=False)
    if error:
        return error

    try:
        issue = _client().get_issue(project_id, issue_id)
        if not issue:
            return f"Issue `{issue_id}` not found in project `{project_id}`."
        lines = [
            f"**{issue.get('name', 'Untitled')}**",
            f"- **ID:** `{issue.get('id')}`",
            f"- **Priority:** {issue.get('priority', 'none')}",
            f"- **State:** {issue.get('state_detail', {}).get('name', 'Unknown') if issue.get('state_detail') else 'Unknown'}",
            f"- **Description:** {issue.get('description_stripped', 'No description')}",
            f"- **Created:** {issue.get('created_at', 'N/A')}",
        ]
        return "\n".join(lines)
    except PlaneNotFoundError:
        return f"Issue `{issue_id}` not found in project `{project_id}`."
    except PlaneAPIError as e:
        logger.error(f"get_issue tool error: {e}")
        return f"Error fetching issue `{issue_id}`: {e.message}"


@tool
def list_labels(project_id: str, config: RunnableConfig) -> str:
    """
    List labels.
    """
    error = validate_project_access(project_id, config, write=False)
    if error:
        return error

    try:
        data = _client().list_labels(project_id)
        labels = data.get("results", []) if isinstance(data, dict) else (data or [])
        if not labels:
            return f"No labels found in project `{project_id}`."
        lines = [f"- **{lbl['name']}** (ID: `{lbl['id']}`)" for lbl in labels]
        return f"Found {len(labels)} label(s):\n" + "\n".join(lines)
    except PlaneAPIError as e:
        logger.error(f"list_labels tool error: {e}")
        return f"Error fetching labels: {e.message}"


# ---------------------------------------------------------------------------
# WRITE tools
# ---------------------------------------------------------------------------


@tool
def create_issue(
    project_id: str,
    title: str,
    description: str = "",
    priority: str = "none",
    config: RunnableConfig = None,
) -> str:
    """
    Create a new issue.
    """
    error = validate_project_access(project_id, config, write=True)
    if error:
        return error
    valid_priorities = {"urgent", "high", "medium", "low", "none"}
    if priority not in valid_priorities:
        priority = "none"

    data = {"name": title, "priority": priority}
    if description:
        data["description"] = description

    try:
        result = _client().create_issue(project_id, data)
        return (
            f"✅ Issue created successfully!\n"
            f"- **Title:** {result.get('name')}\n"
            f"- **ID:** `{result.get('id')}`\n"
            f"- **Priority:** {result.get('priority', 'none')}"
        )
    except PlaneAPIError as e:
        logger.error(f"create_issue tool error: {e}")
        return f"Error creating issue: {e.message}"


@tool
def create_subtask(
    project_id: str,
    parent_issue_id: str,
    title: str,
    description: str = "",
    priority: str = "none",
    config: RunnableConfig = None,
) -> str:
    """
    Create a sub-task.
    """
    error = validate_project_access(project_id, config, write=True)
    if error:
        return error
    valid_priorities = {"urgent", "high", "medium", "low", "none"}
    if priority not in valid_priorities:
        priority = "none"

    data = {"name": title, "priority": priority}
    if description:
        data["description"] = description

    try:
        result = _client().create_subtask(project_id, parent_issue_id, data)
        return (
            f"✅ Sub-task created successfully!\n"
            f"- **Title:** {result.get('name')}\n"
            f"- **ID:** `{result.get('id')}`\n"
            f"- **Parent:** `{parent_issue_id}`\n"
            f"- **Priority:** {result.get('priority', 'none')}"
        )
    except PlaneAPIError as e:
        logger.error(f"create_subtask tool error: {e}")
        return f"Error creating sub-task: {e.message}"


@tool
def update_issue(
    project_id: str, issue_id: str, updates: dict, config: RunnableConfig = None
) -> str:
    """
    Update issue.
    """
    error = validate_project_access(project_id, config, write=True)
    if error:
        return error
    try:
        result = _client().patch_issue(project_id, issue_id, updates)
        updated_fields = ", ".join(updates.keys())
        return (
            f"✅ Issue `{issue_id}` updated successfully!\n"
            f"- **Updated fields:** {updated_fields}\n"
            f"- **New title:** {result.get('name') if result else 'N/A'}"
        )
    except PlaneAPIError as e:
        logger.error(f"update_issue tool error: {e}")
        return f"Error updating issue `{issue_id}`: {e.message}"


@tool
def add_comment(
    project_id: str, issue_id: str, comment: str, config: RunnableConfig = None
) -> str:
    """
    Add comment.
    """
    error = validate_project_access(project_id, config, write=True)
    if error:
        return error
    try:
        _client().add_comment(project_id, issue_id, comment)
        return f"✅ Comment posted to issue `{issue_id}` successfully."
    except PlaneAPIError as e:
        logger.error(f"add_comment tool error: {e}")
        return f"Error adding comment to issue `{issue_id}`: {e.message}"


# ---------------------------------------------------------------------------
# Exported tool list for the agent graph
# ---------------------------------------------------------------------------

PLANE_TOOLS = [
    list_projects,
    list_issues,
    get_issue,
    list_labels,
    create_issue,
    create_subtask,
    update_issue,
    add_comment,
]
