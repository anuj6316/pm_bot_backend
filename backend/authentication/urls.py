from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import UserViewSet, UserAPIKeyViewSet

router = DefaultRouter()
router.register(r"api-keys", UserAPIKeyViewSet, basename="user-api-key")

urlpatterns = [
    # ── User Management (Specific paths first) ────────────────────────
    path("", include(router.urls)),
    path(
        "list_users/",
        UserViewSet.as_view({"get": "list_users"}),
        name="list-users",
    ),
    path(
        "create-user/",
        UserViewSet.as_view({"post": "create_user"}),
        name="create-user",
    ),
    path(
        "set-role/<int:pk>/",
        UserViewSet.as_view({"post": "set_role"}),
        name="set-role",
    ),
    # ── Password & Session ────────────────────────────────────────────
    path(
        "change-password/",
        UserViewSet.as_view({"post": "change_password"}),
        name="change-password",
    ),
    path(
        "logout/",
        UserViewSet.as_view({"post": "logout"}),
        name="logout",
    ),
    path(
        "projects/",
        UserViewSet.as_view({"get": "projects"}),
        name="user-projects",
    ),
    path(
        "set-selected-project/",
        UserViewSet.as_view({"post": "set_selected_project"}),
        name="set-selected-project",
    ),
    # ── Current User Profile (Root match last) ────────────────────────
    path(
        "",
        UserViewSet.as_view(
            {
                "get": "list",
                "put": "update",
                "patch": "partial_update",
            }
        ),
        name="user-profile",
    ),
]
