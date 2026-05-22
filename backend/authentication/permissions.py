from rest_framework import permissions

class DomainRolePermission(permissions.BasePermission):
    """
    Production-grade RBAC permission.
    
    Roles:
    - ADMIN: Full access to everything.
    - DEVELOPER: Read/Write but restricted to specific Plane Project UUIDs.
    - CONSULTANT: Full Read Visibility, but strictly Read-Only for Plane operations.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Superusers and Admins bypass all checks
        if user.is_superuser or user.role == "admin":
            return True

        # Extract project_id from request context
        project_id = (
            request.query_params.get("project_id") or 
            request.data.get("project_id") or
            view.kwargs.get("project_id")
        )

        # CONSULTANT Logic: 
        # - Always allow Read (GET) access to all projects.
        # - Always deny Write (POST/PUT/PATCH/DELETE) on Plane resources.
        if user.role == "consultant":
            if request.method in permissions.SAFE_METHODS:
                return True
            return False  # Read-only enforcement

        # DEVELOPER Logic:
        # - Must have project_id in their authorized list.
        # - If no project_id is provided, we allow it to proceed to the view logic 
        #   (where list/querysets will be filtered by the ViewSet itself).
        if user.role == "developer":
            if project_id:
                return user.has_project_access(project_id)
            return True

        return False


class CanManageUsers(permissions.BasePermission):
    """
    Admin: Full power.
    Consultant: Can manage developers and other consultants. 
    Cannot touch Admins.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
            
        # All authenticated users can read (list/retrieve)
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True
            
        # Write operations restricted to Admin/Consultant
        return user.is_superuser or user.role in ["admin", "consultant"]

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or user.role == "admin":
            return True
        
        # Consultant check
        if user.role == "consultant":
            # Cannot manage Admins or Superusers
            if obj.is_superuser or obj.role == "admin":
                return False
            return True
            
        return False
