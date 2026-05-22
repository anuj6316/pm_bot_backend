"""
JWT authentication middleware for Django Channels WebSocket connections.

Reads a JWT access token from the WebSocket URL query string:
    ws://host/ws/chat/<id>/?token=<access_token>

On success: injects the authenticated User into scope["user"].
On failure: injects AnonymousUser (the consumer rejects the connection).
"""

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken
from jwt import decode as jwt_decode
from django.conf import settings

logger = logging.getLogger(__name__)


@database_sync_to_async
def _get_user_from_id(user_id: int):
    """Resolve user ID → User object. Returns AnonymousUser on miss."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """
    Validates a JWT token from the WebSocket query string.
    Attaches the resolved User to scope["user"] before the consumer runs.
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]

        scope["user"] = AnonymousUser()  # default: unauthenticated

        if token:
            try:
                # Validate the token structure (raises if invalid/expired)
                UntypedToken(token)
                # Decode to extract user_id (HS256 matches SIMPLE_JWT settings)
                decoded = jwt_decode(
                    token,
                    settings.SIMPLE_JWT.get("SIGNING_KEY", settings.SECRET_KEY),
                    algorithms=[settings.SIMPLE_JWT.get("ALGORITHM", "HS256")],
                )
                user_id = decoded.get(settings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id"))
                if user_id:
                    scope["user"] = await _get_user_from_id(user_id)
            except (InvalidToken, TokenError, Exception) as e:
                logger.warning(f"WebSocket JWT validation failed: {e}")
                # scope["user"] stays AnonymousUser

        return await super().__call__(scope, receive, send)


def JwtAuthMiddlewareStack(inner):
    """Convenience wrapper — wraps inner application with JwtAuthMiddleware."""
    return JwtAuthMiddleware(inner)
