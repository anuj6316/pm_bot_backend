"""
Unit tests for the Plane tool functions in chat.agent.tools.

All tests moc;how k PlaneClient so no real Plane API calls are made.
"""

from unittest.mock import patch

from django.test import TestCase
from integrations.plane.exceptions import PlaneAPIError, PlaneAuthError


class ListProjectsToolTest(TestCase):
    @patch("chat.agent.tools.PlaneClient")
    def test_list_projects_success(self, MockClient):
        mock_instance = MockClient.return_value
        mock_instance.list_projects.return_value = {
            "results": [
                {"id": "proj-1", "name": "Backend"},
                {"id": "proj-2", "name": "Frontend"},
            ]
        }

        from chat.agent.tools import list_projects

        result = list_projects.invoke({})

        self.assertIn("Backend", result)
        self.assertIn("proj-1", result)
        self.assertIn("2 project(s)", result)

    @patch("chat.agent.tools.PlaneClient")
    def test_list_projects_empty(self, MockClient):
        mock_instance = MockClient.return_value
        mock_instance.list_projects.return_value = {"results": []}

        from chat.agent.tools import list_projects

        result = list_projects.invoke({})

        self.assertIn("No projects found", result)

    @patch("chat.agent.tools.PlaneClient")
    def test_list_projects_api_error(self, MockClient):
        mock_instance = MockClient.return_value
        mock_instance.list_projects.side_effect = PlaneAuthError("Invalid token")

        from chat.agent.tools import list_projects

        result = list_projects.invoke({})

        self.assertIn("Error", result)
        self.assertIn("Invalid token", result)


class ListIssuesToolTest(TestCase):
    @patch("chat.agent.tools.PlaneClient")
    def test_list_issues_success(self, MockClient):
        mock_instance = MockClient.return_value
        mock_instance.list_issues.return_value = {
            "results": [
                {
                    "id": "issue-1",
                    "name": "Login bug",
                    "priority": "high",
                    "state_detail": {"name": "In Progress"},
                },
            ]
        }

        from chat.agent.tools import list_issues

        result = list_issues.invoke({"project_id": "proj-1"})

        self.assertIn("Login bug", result)
        self.assertIn("high", result)
        self.assertIn("1 issue(s)", result)

    @patch("chat.agent.tools.PlaneClient")
    def test_list_issues_empty(self, MockClient):
        mock_instance = MockClient.return_value
        mock_instance.list_issues.return_value = {"results": []}

        from chat.agent.tools import list_issues

        result = list_issues.invoke({"project_id": "proj-1"})

        self.assertIn("No issues found", result)


class CreateIssueToolTest(TestCase):
    @patch("chat.agent.tools.PlaneClient")
    def test_create_issue_success(self, MockClient):
        mock_instance = MockClient.return_value
        mock_instance.create_issue.return_value = {
            "id": "new-issue-id",
            "name": "Fix the navbar",
            "priority": "high",
        }

        from chat.agent.tools import create_issue

        result = create_issue.invoke(
            {
                "project_id": "proj-1",
                "title": "Fix the navbar",
                "priority": "high",
            }
        )

        self.assertIn("created successfully", result)
        self.assertIn("Fix the navbar", result)
        self.assertIn("new-issue-id", result)
        mock_instance.create_issue.assert_called_once_with(
            "proj-1", {"name": "Fix the navbar", "priority": "high"}
        )

    @patch("chat.agent.tools.PlaneClient")
    def test_create_issue_invalid_priority_defaults_to_none(self, MockClient):
        mock_instance = MockClient.return_value
        mock_instance.create_issue.return_value = {
            "id": "i-1",
            "name": "Test",
            "priority": "none",
        }

        from chat.agent.tools import create_issue

        create_issue.invoke(
            {
                "project_id": "proj-1",
                "title": "Test",
                "priority": "INVALID",
            }
        )

        call_args = mock_instance.create_issue.call_args[0][1]
        self.assertEqual(call_args["priority"], "none")

    @patch("chat.agent.tools.PlaneClient")
    def test_create_issue_api_error(self, MockClient):
        mock_instance = MockClient.return_value
        mock_instance.create_issue.side_effect = PlaneAPIError("Server error")

        from chat.agent.tools import create_issue

        result = create_issue.invoke(
            {
                "project_id": "proj-1",
                "title": "Will fail",
            }
        )

        self.assertIn("Error creating issue", result)


class AddCommentToolTest(TestCase):
    @patch("chat.agent.tools.PlaneClient")
    def test_add_comment_success(self, MockClient):
        mock_instance = MockClient.return_value
        mock_instance.add_comment.return_value = None

        from chat.agent.tools import add_comment

        result = add_comment.invoke(
            {
                "project_id": "proj-1",
                "issue_id": "issue-1",
                "comment": "Fixed in PR #99",
            }
        )

        self.assertIn("posted", result)
        mock_instance.add_comment.assert_called_once_with(
            "proj-1", "issue-1", "Fixed in PR #99"
        )


class UpdateIssueToolTest(TestCase):
    @patch("chat.agent.tools.PlaneClient")
    def test_update_issue_uses_patch(self, MockClient):
        mock_instance = MockClient.return_value
        mock_instance.patch_issue.return_value = {
            "id": "issue-1",
            "name": "Updated Title",
            "priority": "high",
        }

        from chat.agent.tools import update_issue

        result = update_issue.invoke(
            {
                "project_id": "proj-1",
                "issue_id": "issue-1",
                "updates": {"priority": "high"},
            }
        )

        self.assertIn("updated successfully", result)
        # Verify patch_issue was called, NOT update_issue (which would do a full PUT)
        mock_instance.patch_issue.assert_called_once_with(
            "proj-1", "issue-1", {"priority": "high"}
        )
        mock_instance.update_issue.assert_not_called()


class GetIssueToolTest(TestCase):
    @patch("chat.agent.tools.PlaneClient")
    def test_get_issue_success(self, MockClient):
        mock_instance = MockClient.return_value
        mock_instance.get_issue.return_value = {
            "id": "issue-1",
            "name": "Direct Issue",
            "priority": "high",
            "description_stripped": "Issue description",
        }

        from chat.agent.tools import get_issue

        result = get_issue.invoke(
            {
                "project_id": "proj-1",
                "issue_id": "issue-1",
            }
        )

        self.assertIn("Direct Issue", result)
        self.assertIn("Issue description", result)
        mock_instance.get_issue.assert_called_once_with("proj-1", "issue-1")
        mock_instance.list_issues.assert_not_called()

    @patch("chat.agent.tools.PlaneClient")
    def test_get_issue_not_found(self, MockClient):
        from integrations.plane.exceptions import PlaneNotFoundError

        mock_instance = MockClient.return_value
        mock_instance.get_issue.side_effect = PlaneNotFoundError("Not found")

        from chat.agent.tools import get_issue

        result = get_issue.invoke(
            {
                "project_id": "proj-1",
                "issue_id": "issue-missing",
            }
        )

        self.assertIn("not found in project", result)
        mock_instance.get_issue.assert_called_once_with("proj-1", "issue-missing")
