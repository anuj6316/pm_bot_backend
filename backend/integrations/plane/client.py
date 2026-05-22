"""Plane API client for PM Bot integration."""

import logging
import os
from typing import Any

import requests
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .exceptions import (
    PlaneAPIError,
    PlaneAuthError,
    PlaneNotFoundError,
    PlaneValidationError,
)

load_dotenv()

logger = logging.getLogger(__name__)


class PlaneClient:
    """Client for interacting with the Plane API.

    This client provides methods to manage projects, issues, labels, and comments
    in Plane project management system.
    """

    def __init__(self) -> None:
        """Initialize the Plane API client with credentials from environment variables."""
        self.base_url = os.getenv("PLANE_BASE_URL")
        self.token = os.getenv("PLANE_API_TOKEN")
        self.workspace_slug = os.getenv("PLANE_WORKSPACE_SLUG")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-Key": self.token,
                "Content-Type": "application/json",
            }
        )

    @retry(
        retry=retry_if_exception_type(PlaneAPIError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _request(self, method: str, endpoint: str, data: dict | None = None) -> Any:
        """Make an HTTP request to the Plane API.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE).
            endpoint: API endpoint path.
            data: Optional JSON payload for the request.

        Returns:
            Parsed JSON response or None for 204 responses.

        Raises:
            PlaneNotFoundError: When the requested resource is not found (404).
            PlaneAuthError: When authentication fails (401).
            PlaneValidationError: When request validation fails (400).
            PlaneAPIError: For other API errors or network issues.
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, json=data)
            response.raise_for_status()

            if response.status_code == 204 or not response.content:
                return None

            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise PlaneNotFoundError(str(e))
            elif e.response.status_code == 401:
                raise PlaneAuthError(str(e))
            elif e.response.status_code == 400:
                raise PlaneValidationError(str(e))
            else:
                raise PlaneAPIError(str(e))
        except (requests.exceptions.JSONDecodeError, ValueError) as e:
            raise PlaneAPIError(f"Failed to parse JSON response: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise PlaneAPIError(str(e))

    def list_projects(self) -> Any:
        """List all projects in the workspace.

        Returns:
            API response containing project data.
        """
        response = self._request(
            "GET", f"/api/v1/workspaces/{self.workspace_slug}/projects/"
        )
        project_count = len(
            response.get("results", [])
            if isinstance(response, dict)
            else (response or [])
        )
        logger.debug("Plane API list_projects: returned %d projects", project_count)
        return response

    def create_project(self, name: str, identifier: str) -> Any:
        """Create a new project in the workspace.

        Args:
            name: Project name.
            identifier: Project identifier/slug.

        Returns:
            Created project data.
        """
        endpoint = f"/api/v1/workspaces/{self.workspace_slug}/projects/"
        data = {"name": name, "identifier": identifier}
        return self._request("POST", endpoint, data=data)

    def list_issues(self, project_id: str) -> Any:
        """List all issues in a project.

        Args:
            project_id: The project ID to fetch issues from.

        Returns:
            API response containing issue data.
        """
        return self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/issues/",
        )

    def get_issue(self, project_id: str, issue_id: str) -> Any:
        """Retrieve a single issue by its ID.

        Args:
            project_id: The project ID containing the issue.
            issue_id: The issue ID to retrieve.

        Returns:
            Issue data.
        """
        return self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/issues/{issue_id}/",
        )

    def create_issue(self, project_id: str, data: dict) -> Any:
        """Create a new issue in a project.

        Args:
            project_id: The project ID to create the issue in.
            data: Issue data payload.

        Returns:
            Created issue data.
        """
        return self._request(
            "POST",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/issues/",
            data=data,
        )

    def create_subtask(self, project_id: str, parent_issue_id: str, data: dict) -> Any:
        """Create a sub-task (child issue) under an existing issue.

        Args:
            project_id: The project ID.
            parent_issue_id: The parent issue ID.
            data: Subtask data payload.

        Returns:
            Created subtask data.
        """
        data["parent"] = parent_issue_id
        return self._request(
            "POST",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/issues/",
            data=data,
        )

    def list_subtasks(self, project_id: str, parent_issue_id: str) -> Any:
        """List all subtasks (children) of an issue.

        Args:
            project_id: The project ID.
            parent_issue_id: The parent issue ID.

        Returns:
            List of subtasks.
        """
        return self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/issues/"
            f"?parent={parent_issue_id}",
        )

    def replace_issue(self, project_id: str, issue_id: str, data: dict) -> Any:
        """Replace an issue (full replacement).

        Args:
            project_id: The project ID.
            issue_id: The issue ID to update.
            data: Updated issue data.

        Returns:
            Updated issue data.
        """
        return self._request(
            "PUT",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/issues/{issue_id}/",
            data=data,
        )

    def patch_issue(self, project_id: str, issue_id: str, data: dict) -> Any:
        """Partially update an issue (PATCH — only send changed fields).

        Args:
            project_id: The project ID.
            issue_id: The issue ID to update.
            data: Fields to update.

        Returns:
            Updated issue data.
        """
        return self._request(
            "PATCH",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/issues/{issue_id}/",
            data=data,
        )

    def delete_issue(self, project_id: str, issue_id: str) -> None:
        """Delete an issue.

        Args:
            project_id: The project ID.
            issue_id: The issue ID to delete.
        """
        return self._request(
            "DELETE",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/issues/{issue_id}/",
        )

    def add_comment(self, project_id: str, issue_id: str, comment_text: str) -> Any:
        """Add a comment to a Plane issue.

        Args:
            project_id: The project ID.
            issue_id: The issue ID to comment on.
            comment_text: The comment text.

        Returns:
            Created comment data.
        """
        endpoint = f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/issues/{issue_id}/comments/"
        data = {
            "comment_json": {"content": comment_text},
            "comment_html": f"<p>{comment_text}</p>",
        }
        return self._request("POST", endpoint, data=data)

    def list_labels(self, project_id: str) -> Any:
        """List all labels available in a project.

        Args:
            project_id: The project ID.

        Returns:
            List of labels.
        """
        endpoint = (
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/labels/"
        )
        return self._request("GET", endpoint)

    def create_label(self, project_id: str, name: str, color: str = "#ff0000") -> Any:
        """Create a new label in a project.

        Args:
            project_id: The project ID.
            name: Label name.
            color: Label color (hex code).

        Returns:
            Created label data.
        """
        endpoint = (
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/labels/"
        )
        data = {"name": name, "color": color}
        return self._request("POST", endpoint, data=data)

    def add_label_to_issue(
        self, project_id: str, issue_id: str, label_ids: list
    ) -> Any:
        """Attach labels to an issue.

        Args:
            project_id: The project ID.
            issue_id: The issue ID.
            label_ids: List of label IDs to attach.

        Returns:
            Updated issue data.
        """
        endpoint = f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/issues/{issue_id}/"
        data = {"label_ids": label_ids}
        return self._request("PATCH", endpoint, data=data)
