"""
URL configuration for PM Bot backend.

HTTP Routes:
    /admin/                                → Django admin panel
    /api/v1/auth/token/                    → JWT login (POST: {username, password})
    /api/v1/auth/token/refresh/            → JWT refresh (POST: {refresh})
    /api/v1/auth/token/blacklist/          → JWT logout/blacklist (POST: {refresh})
    /api/v1/sessions/                      → Agent issue sessions (read-only)
    /api/v1/issues/                        → Plane issues proxy (read-only)
    /api/v1/chat/conversations/            → Chatbot conversation management
    /api/v1/schema/                        → OpenAPI schema (JSON)
    /api/v1/docs/                          → Swagger UI
    /api/v1/redoc/                         → ReDoc

WebSocket Routes (handled by ASGI/Channels):
    ws://.../ws/chat/new/                  → Start a new conversation
    ws://.../ws/chat/<conversation_id>/    → Resume an existing conversation
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    # Redirect base URL to the Django admin panel
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("admin/", admin.site.urls),
    # ── JWT Authentication ──────────────────────────────────────────
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path(
        "api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"
    ),
    path(
        "api/v1/auth/token/blacklist/",
        TokenBlacklistView.as_view(),
        name="token_blacklist",
    ),
    # ── Modular Apps ────────────────────────────────────────────────
    path("api/v1/user/", include("authentication.urls")),
    path("api/v1/", include("agent.urls")),
    path("api/v1/", include("integrations.urls")),
    path("api/v1/chat/", include("chat.urls")),
    # ── OpenAPI/Swagger Documentation ───────────────────────────────
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/v1/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"
    ),
]
