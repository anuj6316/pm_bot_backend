import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def api_client():
    """Return DRF APIClient instance."""
    return APIClient()


@pytest.fixture
def test_user():
    """Create test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
        username="testuser",
    )


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Return APIClient with valid JWT token."""
    refresh = RefreshToken.for_user(test_user)
    client = api_client
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client
