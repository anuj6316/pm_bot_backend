import pytest
from agent.models import AgentIssueSession


@pytest.mark.django_db
def test_list_sessions(authenticated_client, test_user):
    """GET /api/v1/issues/ returns 200 with paginated results."""
    AgentIssueSession.objects.create(
        plane_issue_id="1",
        status="PENDING",
        created_by=test_user,
    )
    response = authenticated_client.get("/api/v1/sessions/")
    assert response.status_code == 200
    assert "results" in response.data
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_retrieve_session(authenticated_client, test_user):
    """GET /api/v1/issues/{id}/ returns 200 with session data."""
    session = AgentIssueSession.objects.create(
        plane_issue_id="2",
        status="PENDING",
        created_by=test_user,
    )
    response = authenticated_client.get(f"/api/v1/sessions/{session.id}/")
    assert response.status_code == 200
    assert response.data["id"] == session.id
    assert response.data["plane_issue_id"] == "2"


@pytest.mark.django_db
def test_list_sessions_empty(authenticated_client):
    """GET /api/v1/issues/ with no data returns empty list."""
    response = authenticated_client.get("/api/v1/sessions/")
    assert response.status_code == 200
    assert response.data["results"] == []
    assert response.data["count"] == 0


@pytest.mark.django_db
def test_list_sessions_pagination(authenticated_client, test_user):
    """Response includes count, next, previous, results."""
    for i in range(3):
        AgentIssueSession.objects.create(
            plane_issue_id=str(i + 10),
            status="PENDING",
            created_by=test_user,
        )
    response = authenticated_client.get("/api/v1/sessions/")
    assert response.status_code == 200
    assert "count" in response.data
    assert "results" in response.data
    assert response.data["count"] == 3
    assert len(response.data["results"]) == 3
