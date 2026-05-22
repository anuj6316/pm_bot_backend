import pytest
from agent.models import AgentIssueSession


@pytest.mark.django_db
def test_cors_headers_present(authenticated_client, test_user):
    """Response includes Access-Control-Allow-Origin for allowed origin."""
    AgentIssueSession.objects.create(
        plane_issue_id="1",
        status="PENDING",
        created_by=test_user,
    )
    response = authenticated_client.get(
        "/api/v1/issues/",
        HTTP_ORIGIN="http://localhost:3000",
    )
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" in response.headers


@pytest.mark.django_db
def test_cors_preflight(api_client):
    """OPTIONS preflight request returns 200 with CORS headers."""
    response = api_client.options(
        "/api/v1/issues/",
        HTTP_ORIGIN="http://localhost:3000",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
    )
    assert response.status_code == 200
    assert "Access-Control-Allow-Methods" in response.headers


@pytest.mark.django_db
def test_cors_credentials(authenticated_client, test_user):
    """Response includes Access-Control-Allow-Credentials header."""
    AgentIssueSession.objects.create(
        plane_issue_id="1",
        status="PENDING",
        created_by=test_user,
    )
    response = authenticated_client.get(
        "/api/v1/issues/",
        HTTP_ORIGIN="http://localhost:3000",
    )
    assert response.headers.get("Access-Control-Allow-Credentials") == "true"
