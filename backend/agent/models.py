from django.conf import settings
from django.db import models


class AgentIssueSession(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("ARCHIVED", "Archived"),
    ]

    plane_issue_id = models.CharField(max_length=255, unique=True, db_index=True)
    project_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    triage_label = models.CharField(max_length=50, blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    thread_id = models.CharField(max_length=255, blank=True, null=True)
    error_log = models.TextField(blank=True, null=True)
    draft_response = models.TextField(blank=True, null=True, help_text="Stores the AI's draft response for review")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_sessions",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session {self.plane_issue_id} ({self.status})"

    class Meta:
        verbose_name = "Agent Issue Session"
        verbose_name_plural = "Agent Issue Sessions"
        ordering = ["-updated_at"]
        db_table = "deep_agent_agentissuesession"
