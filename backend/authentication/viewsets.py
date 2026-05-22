import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from .serializers import (
    UserProfileSerializer,
    ChangePasswordSerializer,
    SetRoleSerializer,
    UserCreateSerializer,
    ProjectSerializer,
    SelectedProjectSerializer,
    UserAPIKeySerializer,
)
from .permissions import CanManageUsers

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ViewSet):
    """
    ViewSet for User Profile management, Password Change, and Logout.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "change_password":
            return ChangePasswordSerializer
        if self.action == "set_role":
            return SetRoleSerializer
        if self.action == "create_user":
            return UserCreateSerializer
        return UserProfileSerializer

    @extend_schema(
        summary="List user projects",
        description="Returns projects from Plane that the user has access to. Admins/Consultants see all projects.",
        responses={200: ProjectSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="projects")
    def projects(self, request):
        """GET /api/v1/user/projects/ - List projects user has access to"""
        from integrations.plane.client import PlaneClient

        try:
            plane = PlaneClient()
            plane_res = plane.list_projects() or []

            # Handle Plane pagination
            if isinstance(plane_res, dict) and "results" in plane_res:
                all_projects = plane_res["results"]
            elif isinstance(plane_res, list):
                all_projects = plane_res
            else:
                all_projects = []

            # For developers, filter by their assigned projects
            if request.user.role in ["developer"] and not request.user.is_superuser:
                allowed_ids = request.user.get_allowed_projects()

                logger.info(
                    "Project filtering: user=%s role=%s is_superuser=%s allowed_ids=%s",
                    request.user.email,
                    request.user.role,
                    request.user.is_superuser,
                    allowed_ids,
                )
                logger.debug("Total projects from Plane API: %d", len(all_projects))

                # Log first 3 projects as sample
                for i, p in enumerate(all_projects[:3]):
                    logger.debug(
                        "Plane project[%d]: id=%s identifier=%s name=%s",
                        i,
                        p.get("id"),
                        p.get("identifier"),
                        p.get("name"),
                    )

                filtered_projects = [
                    p
                    for p in all_projects
                    if str(p.get("id", "")).lower()
                    in [str(aid).lower() for aid in allowed_ids]
                ]

                logger.info(
                    "Filtered projects: %d (from %d total)",
                    len(filtered_projects),
                    len(all_projects),
                )

                for p in filtered_projects:
                    logger.info(
                        "  → Including: id=%s name=%s", p.get("id"), p.get("name")
                    )

                return Response(
                    {"msg": "Projects fetched successfully", "data": filtered_projects}
                )

            # Admins and Consultants see all projects
            return Response(
                {"msg": "Projects fetched successfully", "data": all_projects}
            )

        except Exception as e:
            return Response(
                {"msg": "Failed to fetch projects", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Set selected project",
        description="Store the user's currently selected project in their profile.",
        request=SelectedProjectSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(detail=False, methods=["post"], url_path="set-selected-project")
    def set_selected_project(self, request):
        """POST /api/v1/user/set-selected-project/ - Set user's selected project"""
        serializer = SelectedProjectSerializer(data=request.data)
        if serializer.is_valid():
            project_id = serializer.validated_data.get("project_id")

            # Verify user has access to this project
            if not request.user.has_project_access(project_id):
                return Response(
                    {"msg": "You don't have access to this project"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            request.user.selected_project = project_id
            request.user.save(update_fields=["selected_project"])
            return Response({"msg": "Selected project updated successfully"})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserAPIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user API keys.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserAPIKeySerializer

    def get_queryset(self):
        from .models import UserAPIKey
        return UserAPIKey.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        from .models import UserAPIKey
        # Update if already exists for this provider
        provider = serializer.validated_data.get('provider')
        existing = UserAPIKey.objects.filter(user=self.request.user, provider=provider).first()
        if existing:
            serializer.instance = existing
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def providers(self, request):
        """List available providers for API keys"""
        from .models import UserAPIKey
        return Response([{"id": c[0], "label": c[1]} for c in UserAPIKey.Provider.choices])

    def list(self, request):
        """GET /api/v1/user/ - Get current user profile"""
        serializer = UserProfileSerializer(request.user)
        return Response(
            {"msg": "User profile fetched successfully", "data": serializer.data}
        )

    def update(self, request):
        """PUT /api/v1/user/ - Update current user profile"""
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=False
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"msg": "User profile updated successfully", "data": serializer.data}
            )
        return Response(
            {"msg": "Failed to update profile", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def partial_update(self, request):
        """PATCH /api/v1/user/ - Partial update current user profile"""
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"msg": "User profile updated successfully", "data": serializer.data}
            )
        return Response(
            {"msg": "Failed to update profile", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        """POST /api/v1/user/change-password/ - Change user password"""
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data.get("old_password")):
                return Response(
                    {"msg": "Old password is incorrect"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.set_password(serializer.validated_data.get("new_password"))
            user.save()

            return Response({"msg": "Password changed successfully"})

        return Response(
            {"msg": "Failed to change password", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["post"])
    def logout(self, request):
        """POST /api/v1/user/logout/ - Logout user and blacklist tokens"""
        try:
            refresh_token = request.data.get("refresh_token")
            if refresh_token:
                from rest_framework_simplejwt.tokens import RefreshToken

                token = RefreshToken(refresh_token)
                token.blacklist()

            return Response({"msg": "Logged out successfully"})
        except Exception:
            return Response({"msg": "Logged out"}, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # User Management (Admin/Consultant only)
    # ------------------------------------------------------------------

    @extend_schema(
        summary="List all users",
        responses={200: UserProfileSerializer(many=True)},
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated, CanManageUsers],
    )
    def list_users(self, request):
        """GET /api/v1/user/list_users/ - List users in the system (filtered by role)"""
        from django.contrib.auth import get_user_model
        from django.db.models import Q

        User = get_user_model()

        # If Admin/Consultant/Superuser: see all
        if request.user.role in ["admin", "consultant"] or request.user.is_superuser:
            users = User.objects.all().order_by("-date_joined")
        else:
            # Developers only see users who share at least one project
            user_projects = request.user.get_allowed_projects()
            if not user_projects:
                # If no projects assigned, they at least see themselves
                users = User.objects.filter(pk=request.user.pk)
            else:
                # Matches any user where their projects list contains ANY item from the requester's list
                query = Q(pk=request.user.pk)  # Always see self
                for p_id in user_projects:
                    query |= Q(projects__contains=p_id)
                users = User.objects.filter(query).distinct().order_by("-date_joined")

        serializer = UserProfileSerializer(users, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Set user role",
        request=SetRoleSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="set-role",
        permission_classes=[IsAuthenticated, CanManageUsers],
    )
    def set_role(self, request, pk=None):
        """POST /api/v1/user/{id}/set-role/ - Set role for a specific user"""
        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            target_user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"msg": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # DRF check_object_permissions manually since this is a ViewSet action on detail
        self.check_object_permissions(request, target_user)

        serializer = SetRoleSerializer(data=request.data)
        if serializer.is_valid():
            new_role = serializer.validated_data["role"]

            # Additional Security Check: Consultant cannot promote to Admin
            if request.user.role == "consultant" and new_role == "admin":
                return Response(
                    {"msg": "Consultants cannot promote users to Admin role."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            target_user.role = new_role
            target_user.save()
            return Response(
                {"msg": f"Role updated to {new_role} for {target_user.email}"}
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Create new user",
        request=UserCreateSerializer,
        responses={201: UserProfileSerializer},
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="create-user",
        permission_classes=[permissions.IsAuthenticated, CanManageUsers],
    )
    def create_user(self, request):
        """POST /api/v1/user/create-user/ - Create a new account manually"""
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            new_role = serializer.validated_data.get("role", "developer")

            # Security: Consultant cannot create an Admin
            if request.user.role == "consultant" and new_role == "admin":
                return Response(
                    {"msg": "Consultants are not authorized to create Admin accounts."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            user = serializer.save()
            return Response(
                {
                    "msg": "Account created successfully",
                    "data": UserProfileSerializer(user).data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
