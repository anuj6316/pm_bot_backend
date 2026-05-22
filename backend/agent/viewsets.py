from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from .models import AgentIssueSession
from .serializers import SessionSerializer
from .tasks import trigger_manual_sync


@extend_schema(tags=["Sessions"])
class SessionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Expose agent session states to React dashboard.
    Requires JWT authentication for all operations.
    Optimized to prevent N+1 queries.
    """

    queryset = AgentIssueSession.objects.all().order_by("-created_at")
    serializer_class = SessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filter sessions:
        1. Only those created by the current user.
        2. (Optional) Filter by project if project mapping is added to sessions.
        """
        user = self.request.user
        if user.is_superuser:
            return super().get_queryset()

        # In this multi-tenant setup, sessions must be owned by the requester
        return super().get_queryset().filter(created_by=user)

    @extend_schema(
        summary="Approve session",
        description="Approve a completed session to trigger the final Plane integration.",
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """
        Approve a completed session. This triggers the process_approved_session task.
        """
        session = self.get_object()

        if session.status != "COMPLETED":
            return Response(
                {"error": "Only completed sessions can be approved"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if session.is_approved:
            return Response(
                {"error": "Session is already approved"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark as approved and trigger the final integration task
        session.is_approved = True
        session.save(update_fields=["is_approved", "updated_at"])

        # Trigger the approved session processing task
        from .tasks import process_approved_session

        process_approved_session.delay(session.id)

        return Response({"status": "Session approved", "is_approved": True})

    @extend_schema(
        summary="Sync session",
        description="Trigger manual sync/re-analysis for a specific session.",
        responses={202: OpenApiTypes.OBJECT},
    )
    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        """
        Trigger manual sync/re-analysis for a specific session.
        """
        session = self.get_object()
        trigger_manual_sync.delay(session.id)
        return Response({"status": "Sync triggered"}, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        summary="Get session logs",
        description="Stream reasoning logs via Server-Sent Events (SSE).",
        responses={200: OpenApiTypes.STR},
    )
    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        """
        Stream reasoning logs via SSE.
        """
        from django.http import StreamingHttpResponse
        import time

        def event_stream():
            session = self.get_object()
            # Placeholder for actual log streaming logic
            yield f"data: Initializing logs for session {session.id}\n\n"
            time.sleep(1)
            yield "data: Reasoning process started...\n\n"
            time.sleep(1)
            yield f"data: Status: {session.status}\n\n"

        return StreamingHttpResponse(event_stream(), content_type="text/event-stream")
