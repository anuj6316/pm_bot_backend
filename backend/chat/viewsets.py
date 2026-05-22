import os
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import Conversation
from .serializers import (
    ConversationSerializer,
    ConversationDetailSerializer,
    MessageSerializer,
)
from .agent.graph import ALLOWED_MODELS, _DEFAULT_MODEL
from .agent.query_graph import run_query
from authentication.models import UserAPIKey

_MODEL_META: dict[str, dict] = {
    "groq/llama-3.3-70b-versatile": {
        "label": "Llama 3.3 70B",
        "provider": "Groq",
        "badge": "Fast · Free tier",
        "env_var": "GROQ_API_KEY",
    },
    "groq/llama3-8b-8192": {
        "label": "Llama 3 8B",
        "provider": "Groq",
        "badge": "Fastest",
        "env_var": "GROQ_API_KEY",
    },
    "groq/mixtral-8x7b-32768": {
        "label": "Mixtral 8x7B",
        "provider": "Groq",
        "badge": "Long context",
        "env_var": "GROQ_API_KEY",
    },
    "openai/gpt-4o-mini": {
        "label": "GPT-4o mini",
        "provider": "OpenAI",
        "badge": "Recommended",
        "env_var": "OPENAI_API_KEY",
    },
    "openai/gpt-4o": {
        "label": "GPT-4o",
        "provider": "OpenAI",
        "badge": "Most capable",
        "env_var": "OPENAI_API_KEY",
    },
    "anthropic/claude-3-5-haiku-20241022": {
        "label": "Claude 3.5 Haiku",
        "provider": "Anthropic",
        "badge": "Fast",
        "env_var": "ANTHROPIC_API_KEY",
    },
    "anthropic/claude-3-5-sonnet-20241022": {
        "label": "Claude 3.5 Sonnet",
        "provider": "Anthropic",
        "badge": "Balanced",
        "env_var": "ANTHROPIC_API_KEY",
    },
    "gemini/gemini-1.5-flash": {
        "label": "Gemini 1.5 Flash",
        "provider": "Google",
        "badge": "Fast",
        "env_var": "GEMINI_API_KEY",
    },
    "gemini/gemini-2.0-flash": {
        "label": "Gemini 2.0 Flash",
        "provider": "Google",
        "badge": "Latest",
        "env_var": "GEMINI_API_KEY",
    },
    "ollama/llama3.2": {
        "label": "Llama 3.2",
        "provider": "Ollama",
        "badge": "Local",
        "env_var": None,
    },
    "ollama/mistral": {
        "label": "Mistral",
        "provider": "Ollama",
        "badge": "Local",
        "env_var": None,
    },
}


@extend_schema(tags=["Chat"])
class ChatModelViewSet(viewsets.ViewSet):
    """
    ViewSet for retrieving available LLM models.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """
        GET /api/v1/chat/models/
        """
        user_keys = {
            k.provider: k.api_key for k in UserAPIKey.objects.filter(user=request.user)
        }
        
        result = []
        for model_id in ALLOWED_MODELS:
            meta = _MODEL_META.get(model_id, {})
            env_var = meta.get("env_var")
            provider = meta.get("provider")
            
            # Available if system key exists OR user has provided their own key for this provider
            system_available = (env_var is None) or bool(os.environ.get(env_var, "").strip())
            user_available = provider in user_keys
            
            result.append(
                {
                    "id": model_id,
                    "label": meta.get("label", model_id),
                    "provider": provider,
                    "badge": meta.get("badge", ""),
                    "env_var": env_var,
                    "available": system_available or user_available,
                    "is_default": model_id == _DEFAULT_MODEL,
                }
            )
        return Response(result)


@extend_schema(tags=["Chat"])
class ChatQueryViewSet(viewsets.ViewSet):
    """
    ViewSet for high-level system queries.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Chat Interface Model",
        description="Resolving user query based on the user's ORM and Plane context.",
    )
    @action(detail=False, methods=['post'])
    def query(self, request):
        query = request.data.get("query")
        model_name = request.data.get("model")

        if not query:
            return Response({"error": "Query is required"}, status=400)

        answer = run_query(
            query=query,
            user_id=request.user.id,
            user_role=request.user.role,
            allowed_projects=request.user.projects or [],
            model_name=model_name
        )

        return Response({
            "query": query,
            "answer": answer,
            "source": "orchestrator"
        })

@extend_schema(tags=["Chat"])
class ConversationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user conversations and message history.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ConversationDetailSerializer
        return ConversationSerializer

    def get_queryset(self):
        return (
            Conversation.objects.filter(user=self.request.user)
            .prefetch_related("messages")
            .order_by("-updated_at")
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        """
        GET /api/v1/chat/conversations/<pk>/messages/
        Returns full message history for the specific conversation.
        """
        conversation = self.get_object()
        messages = conversation.messages.order_by("created_at")
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)
