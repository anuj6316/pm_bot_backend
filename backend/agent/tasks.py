import logging

from celery import shared_task
from integrations.plane.client import PlaneClient

from .brain.graph import run_brain
from .models import AgentIssueSession

logger = logging.getLogger(__name__)


@shared_task(name="agent.tasks.poll_plane_issues")
def poll_plane_issues():
    """
    Periodic task to poll Plane for new/unprocessed issues.
    """
    client = PlaneClient()
    logger.info("Starting Plane polling task...")

    try:
        # 1. Get all projects in the workspace
        projects = client.list_projects()
        results = (
            projects.get("results", [])
            if isinstance(projects, dict)
            else (projects or [])
        )
        logger.info(f"Found {len(results)} projects to scan.")

        for project in results:
            project_id = project.get("id")

            # 2. Get issues for each project
            issues_data = client.list_issues(project_id)
            issues = (
                issues_data.get("results", [])
                if isinstance(issues_data, dict)
                else (issues_data or [])
            )

            for issue in issues:
                issue_id = issue.get("id")
                issue_title = issue.get("name", "")
                issue_body = issue.get("description_stripped", "")
                full_content = f"Title: {issue_title}\nDescription: {issue_body}"

                # 3. Check if we already have a session for this issue
                session, created = AgentIssueSession.objects.get_or_create(
                    plane_issue_id=issue_id,
                    defaults={
                        "project_id": project_id,
                        "status": "PENDING",
                        "is_approved": False,
                        "triage_label": "",
                    },
                )

                # Backfill project_id for existing sessions
                if not created and not session.project_id:
                    session.project_id = project_id
                    # The session will be saved at the end of the loop

                if created:
                    logger.info(f"New issue discovered: {issue_id}. Executing brain...")
                    session.status = "PROCESSING"
                    session.save()

                    # 4. Run the reasoning workflow
                    result = run_brain(full_content)

                    if result.get("error"):
                        session.status = "FAILED"
                        session.error_log = result["error"]
                    else:
                        session.status = "COMPLETED"
                        session.triage_label = result.get(
                            "category", "QUESTION"
                        ).upper()
                        # Store only the draft response in draft_response field for review
                        session.draft_response = result.get("draft_response", "")
                        session.thread_id = "test-thread"

                    session.save()
                    logger.info(
                        f"Brain execution complete for issue {issue_id}. Status: {session.status}"
                    )
                else:
                    session.save()

    except Exception as e:
        logger.error(f"Error during Plane polling: {str(e)}")
        raise e

    logger.info("Plane polling task completed.")
    return "Polling Complete"


@shared_task(name="agent.tasks.process_approved_session")
def process_approved_session(session_id):
    """
    Final integration task: Posts the approved comment and adds labels to Plane.
    """
    try:
        session = AgentIssueSession.objects.get(id=session_id)
        if not session.is_approved:
            logger.warning(f"Session {session_id} is not approved yet. Skipping.")
            return "Skipped: Not Approved"

        client = PlaneClient()
        logger.info(
            f"Posting approved session {session_id} for issue {session.plane_issue_id} to Plane..."
        )

        # 1. Identify the project for this issue
        target_project_id = session.project_id

        # Fallback for old sessions that lack a project_id
        if not target_project_id:
            logger.info(
                "project_id missing on session, falling back to scanning projects..."
            )
            projects_data = client.list_projects()
            projects = (
                projects_data.get("results", [])
                if isinstance(projects_data, dict)
                else (projects_data or [])
            )
            for p in projects:
                issues_data = client.list_issues(p["id"])
                issues = (
                    issues_data.get("results", [])
                    if isinstance(issues_data, dict)
                    else (issues_data or [])
                )
                if any(i["id"] == session.plane_issue_id for i in issues):
                    target_project_id = p["id"]
                    session.project_id = target_project_id
                    session.save(update_fields=["project_id"])
                    break

        if not target_project_id:
            raise Exception("Could not find project_id for issue.")

        # 2. Handle Labels (Synchronize BUG/FEATURE/QUESTION)
        label_name = session.triage_label or "QUESTION"
        labels_data = client.list_labels(target_project_id)
        # Handle cases where results are nested differently
        labels_list = (
            labels_data.get("results", [])
            if isinstance(labels_data, dict)
            else labels_data
        )

        label_id = next(
            (
                label["id"]
                for label in labels_list
                if label["name"].upper() == label_name.upper()
            ),
            None,
        )

        if not label_id:
            logger.info(f"Label '{label_name}' not found in project. Creating it...")
            colors = {"BUG": "#ff0000", "FEATURE": "#3d96fb", "QUESTION": "#fbc43d"}
            new_label = client.create_label(
                target_project_id, label_name, colors.get(label_name, "#cccccc")
            )
            label_id = new_label["id"]

        # 3. Attach Label
        client.add_label_to_issue(target_project_id, session.plane_issue_id, [label_id])

        # 4. Post Comment - use draft_response instead of error_log
        client.add_comment(target_project_id, session.plane_issue_id, session.draft_response or "")

        # 5. Finalize
        session.status = "ARCHIVED"
        session.save()
        logger.info(f"Successfully posted issue {session.plane_issue_id} to Plane.")
        return "Post Successful"

    except Exception as e:
        logger.error(f"Error processing approved session {session_id}: {str(e)}")
        if "session" in locals():
            session.status = "FAILED"
            session.error_log = f"Final Post Failed: {str(e)}"
            session.save()
        raise e


@shared_task(name="agent.tasks.trigger_manual_sync")
def trigger_manual_sync(session_id):
    """
    Triggers a re-analysis of a session manually.
    """
    logger.info(f"Manual sync requested for session {session_id}")
    session = AgentIssueSession.objects.get(id=session_id)
    session.status = "PROCESSING"
    session.save()
    # Logic to re-trigger analysis
    return "Sync initiated"
