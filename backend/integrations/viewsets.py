import logging
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiTypes

from authentication.permissions import DomainRolePermission
from .plane.client import PlaneClient
from .plane.exceptions import PlaneAPIError

logger = logging.getLogger(__name__)


@extend_schema(tags=["Issues"])
class IssueViewSet(viewsets.ViewSet):
    """
    Retrieve issues from Plane, organized by project.
    Strictly enforced by User Role and authorization list.
    """

    permission_classes = [permissions.IsAuthenticated, DomainRolePermission]

    def _get_all_projects_and_issues(self, request):
        """
        Fetch all projects + their issues from Plane, then filter by user access.
        """
        user = request.user
        allowed_ids = user.get_allowed_projects()

        # Performance optimization: if restricted and list is empty, return early
        if allowed_ids is not None and not allowed_ids:
            return [], {}

        client = PlaneClient()
        try:
            projects_data = client.list_projects()
            all_projects = (
                projects_data.get("results", [])
                if isinstance(projects_data, dict)
                else (projects_data or [])
            )
        except PlaneAPIError as e:
            logger.error(f"Failed to fetch projects: {e}")
            return [], {}

        # Filter projects based on user access
        projects = [
            p
            for p in all_projects
            if allowed_ids is None
            or str(p.get("id")).lower() in [str(aid).lower() for aid in allowed_ids]
        ]

        logger.info(
            "Project filtering for user %s: allowed_ids=%s, total=%d, filtered=%d",
            request.user.email,
            allowed_ids,
            len(all_projects),
            len(projects),
        )

        grouped = {}
        for project in projects:
            pid = project.get("id")
            pname = project.get("name", "Unknown Project")
            pidentifier = project.get("identifier", "")
            try:
                issues_data = client.list_issues(pid)
                issues = (
                    issues_data.get("results", [])
                    if isinstance(issues_data, dict)
                    else (issues_data or [])
                )
            except PlaneAPIError as e:
                logger.warning(f"Failed to fetch issues for project {pid}: {e}")
                issues = []

            # Embed project context into each issue
            enriched = []
            for issue in issues:
                enriched.append(
                    {
                        "id": issue.get("id"),
                        "sequence_id": issue.get("sequence_id"),
                        "name": issue.get("name", ""),
                        "description": issue.get("description_stripped", "") or "",
                        "priority": issue.get("priority", "none"),
                        "state": (issue.get("state_detail") or {}).get(
                            "name", "Unknown"
                        ),
                        "state_group": (issue.get("state_detail") or {}).get(
                            "group", ""
                        ),
                        "assignees": issue.get("assignee_ids", []),
                        "label_ids": issue.get("label_ids", []),
                        "created_at": issue.get("created_at"),
                        "updated_at": issue.get("updated_at"),
                        "project_id": pid,
                        "project_name": pname,
                        "project_identifier": pidentifier,
                    }
                )

            grouped[pid] = {
                "project": {
                    "id": pid,
                    "name": pname,
                    "identifier": pidentifier,
                    "issue_count": len(enriched),
                },
                "issues": enriched,
            }

        return projects, grouped

    @extend_schema(
        summary="List all issues",
        description="Retrieve a flat list of all issues from all Plane projects with project information.",
        responses={200: OpenApiTypes.OBJECT},
    )
    def list(self, request):
        """GET /api/v1/issues/ — flat list of all issues across all projects."""
        _, grouped = self._get_all_projects_and_issues(request)
        all_issues = []
        for group in grouped.values():
            all_issues.extend(group["issues"])
        return Response(all_issues)

    @extend_schema(
        summary="List issues by project",
        description="Returns issues grouped by project. Useful for hierarchical views.",
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(detail=False, methods=["get"], url_path="by_project")
    def by_project(self, request):
        """
        GET /api/v1/issues/by_project/
        """
        _, grouped = self._get_all_projects_and_issues(request)
        result = sorted(grouped.values(), key=lambda g: g["project"]["name"])
        return Response(result)

    @extend_schema(
        summary="Create a new issue",
        description="Create a new issue in a Plane project.",
        request=OpenApiTypes.OBJECT,
        responses={201: OpenApiTypes.OBJECT},
    )
    @action(detail=False, methods=["post"], url_path="create")
    def create_issue(self, request):
        """
        POST /api/v1/issues/create/
        """
        project_id = request.data.get("project_id")
        name = request.data.get("name", "").strip()
        if not project_id or not name:
            return Response(
                {"error": "project_id and name are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = {
            "name": name,
            "priority": request.data.get("priority", "none"),
        }
        if request.data.get("description"):
            data["description"] = request.data["description"]

        try:
            result = PlaneClient().create_issue(project_id, data)
            return Response(result, status=status.HTTP_201_CREATED)
        except PlaneAPIError as e:
            logger.error(f"create_issue error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    @extend_schema(
        summary="Create a sub-task",
        description="Create a sub-task under an existing issue.",
        request=OpenApiTypes.OBJECT,
        responses={201: OpenApiTypes.OBJECT},
    )
    @action(detail=False, methods=["post"], url_path="create_subtask")
    def create_subtask(self, request):
        """
        POST /api/v1/issues/create_subtask/
        """
        project_id = request.data.get("project_id")
        parent_issue_id = request.data.get("parent_issue_id")
        name = request.data.get("name", "").strip()

        if not project_id or not parent_issue_id or not name:
            return Response(
                {"error": "project_id, parent_issue_id, and name are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = {
            "name": name,
            "priority": request.data.get("priority", "none"),
        }
        if request.data.get("description"):
            data["description"] = request.data["description"]

        try:
            result = PlaneClient().create_subtask(project_id, parent_issue_id, data)
            return Response(result, status=status.HTTP_201_CREATED)
        except PlaneAPIError as e:
            logger.error(f"create_subtask error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
