"""
ASGI config for backend project.

Handles both HTTP (Django) and WebSocket (Django Channels) traffic via
ProtocolTypeRouter. WebSocket connections are authenticated via JWT middleware.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

# get_asgi_application() must be called before importing any Django-dependent code
from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

# ─── Disable MLflow autologging for LangChain/LangGraph ──────────────────────
# Root cause: MLflow patches LangChain callbacks and creates asyncio ContextVar
# tokens in the main thread. When Daphne processes WebSocket messages it spawns
# new asyncio tasks (copies of the current context). Python's asyncio then
# prevents resetting ContextVar tokens across async context boundaries, producing:
#   "ContextVar token was created in a different Context"
# Disabling autologging here (post django-setup, pre request-handling) prevents
# those tokens from ever being created while still allowing explicit mlflow calls.
try:
    import mlflow
    mlflow.langchain.autolog(disable=True)
except Exception:
    pass  # mlflow not installed — safe to skip

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from chat.middleware import JwtAuthMiddlewareStack  # noqa: E402
from chat.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        # Standard Django HTTP handling
        "http": django_asgi_app,
        # WebSocket: validate origin → JWT auth → route to consumer
        "websocket": AllowedHostsOriginValidator(
            JwtAuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    }
)
