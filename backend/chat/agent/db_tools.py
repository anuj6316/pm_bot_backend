"""
Database-centric tools for the QueryOrchestrator.
These tools use the Django ORM to provide the local "Source of Truth".
"""

import logging
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from django.contrib.auth import get_user_model
from agent.models import AgentIssueSession
from django.db.models import Count, Q

logger = logging.getLogger(__name__)
User = get_user_model()

@tool
def get_user_info(config: RunnableConfig) -> str:
    """
    Get the current user's role and project assignments from the local database.
    Use this to verify what projects the user is authorized to query about.
    """
    conf = config.get("configurable", {})
    user_id = conf.get("user_id")
    
    try:
        user = User.objects.get(id=user_id)
        projects = user.projects or []
        return (
            f"User Profile (Local DB):\n"
            f"- Email: {user.email}\n"
            f"- Role: {user.role}\n"
            f"- Assigned Projects: {', '.join(projects) if projects else 'None (Global Access if Admin)'}\n"
            f"- Is Superuser: {user.is_superuser}"
        )
    except User.DoesNotExist:
        return "Error: User not found in local database."

@tool
def get_internal_session_status(project_id: str = None) -> str:
    """
    Queries the AgentIssueSession table to find the status of AI processing tasks.
    Use this when the user asks about the 'status', 'failure', or 'progress' of AI tasks.
    """
    try:
        sessions = AgentIssueSession.objects.all()
        if project_id:
            # Match project_id in plane_issue_id (which usually contains project identifier)
            sessions = sessions.filter(plane_issue_id__icontains=project_id)

        stats = sessions.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='PENDING')),
            processing=Count('id', filter=Q(status='PROCESSING')),
            completed=Count('id', filter=Q(status='COMPLETED')),
            failed=Count('id', filter=Q(status='FAILED'))
        )

        if stats['total'] == 0:
            return "No AI processing sessions found in the local database."

        res = [
            "AI Processing Stats (Local DB):",
            f"- Total Sessions: {stats['total']}",
            f"- Completed: {stats['completed']}",
            f"- Processing: {stats['processing']}",
            f"- Pending: {stats['pending']}",
            f"- Failed: {stats['failed']}"
        ]
        
        # If there are failures, list the most recent one's error
        if stats['failed'] > 0:
            last_failed = sessions.filter(status='FAILED').order_by('-updated_at').first()
            if last_failed and last_failed.error_log:
                res.append(f"\nRecent Error Log for `{last_failed.plane_issue_id}`:\n{last_failed.error_log[:200]}...")

        return "\n".join(res)
    except Exception as e:
        logger.error(f"get_internal_session_status error: {e}")
        return f"Error querying local sessions: {str(e)}"

@tool
def list_local_users(config: RunnableConfig) -> str:
    """
    Lists other users in the system. Use this if the user asks 'who else is on the team' 
    or 'who are the admins'.
    """
    try:
        users = User.objects.all().only('email', 'role', 'username')
        lines = [f"- {u.username} ({u.email}) | Role: {u.role}" for u in users]
        return "Team Members (Local DB):\n" + "\n".join(lines)
    except Exception as e:
        return f"Error listing users: {str(e)}"

# Collection of DB-only tools
DB_TOOLS = [
    get_user_info,
    get_internal_session_status,
    list_local_users,
]
