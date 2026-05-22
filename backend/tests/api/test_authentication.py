import pytest
from rest_framework_simplejwt.tokens import RefreshToken
from agent.models import AgentIssueSession


@pytest.mark.django_db
def test_unauthorized_access(api_client):
    """GET /api/v1/issues/ without token returns 401."""
    response = api_client.get("/api/v1/issues/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_authorized_access(authenticated_client, test_user):
    """GET /api/v1/issues/ with valid token returns 200."""
    AgentIssueSession.objects.create(
        plane_issue_id="1",
        status="PENDING",
        created_by=test_user,
    )
    response = authenticated_client.get("/api/v1/issues/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_invalid_token(api_client):
    """GET /api/v1/issues/ with invalid token returns 401."""
    api_client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")
    response = api_client.get("/api/v1/issues/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_token_blacklist(authenticated_client, test_user):
    """POST to token blacklist invalidates refresh token."""
    refresh = RefreshToken.for_user(test_user)
    response = authenticated_client.post(
        "/api/v1/auth/token/blacklist/",
        {"refresh": str(refresh)},
    )
    assert response.status_code == 200
