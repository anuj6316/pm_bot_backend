from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import SessionViewSet

router = DefaultRouter()
router.register(r"sessions", SessionViewSet, basename="session")

urlpatterns = [
    path("", include(router.urls)),
]
