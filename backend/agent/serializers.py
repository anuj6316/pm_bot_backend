from rest_framework import serializers
from .models import AgentIssueSession


class SessionSerializer(serializers.ModelSerializer):
    """
    Expose AgentIssueSession state to React dashboard.
    Read-only access for monitoring session progress.
    """

    class Meta:
        model = AgentIssueSession
        fields = [
            "id",
            "plane_issue_id",
            "status",
            "triage_label",
            "is_approved",
            "created_by",
            "thread_id",
            "error_log",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
