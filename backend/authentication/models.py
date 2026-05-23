from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        DEVELOPER = "developer", "Developer"
        CONSULTANT = "consultant", "Consultant"

    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.DEVELOPER,
    )

    # List of Plane Project UUID codes the user can access (only used for DEVELOPER).
    projects = models.JSONField(
        default=list, blank=True, help_text="List of Plane Project UUIDs"
    )

    # Currently selected project ID (stored for persistence across browsers)
    selected_project = models.CharField(max_length=100, blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email

    def has_project_access(self, project_id: str) -> bool:
        if self.role in [self.Role.ADMIN, self.Role.CONSULTANT] or self.is_superuser:
            return True
        if not project_id:
            return False
        return str(project_id).lower() in [str(p).lower() for p in self.projects]

    def get_allowed_projects(self) -> list[str]:
        """Return the list of project IDs this user is authorized to interact with."""
        # Admin/Consultant/Superuser have access to ALL projects (None means no filtering)
        if self.role in [self.Role.ADMIN, self.Role.CONSULTANT] or self.is_superuser:
            return None
        return self.projects or []


from fernet_fields import EncryptedCharField


class UserAPIKey(models.Model):
    """
    Stores API keys provided by the user for different LLM providers.
    """

    class Provider(models.TextChoices):
        OPENAI = "OpenAI", "OpenAI"
        GROQ = "Groq", "Groq"
        ANTHROPIC = "Anthropic", "Anthropic"
        GOOGLE = "Google", "Google"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    provider = models.CharField(max_length=50, choices=Provider.choices)
    api_key = EncryptedCharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "provider")
        verbose_name = "User API Key"
        verbose_name_plural = "User API Keys"

    def __str__(self):
        return f"{self.user.email} - {self.provider}"
