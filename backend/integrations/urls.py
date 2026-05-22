from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import IssueViewSet

router = DefaultRouter()
router.register(r"issues", IssueViewSet, basename="issue")

urlpatterns = [
    path("", include(router.urls)),
]
