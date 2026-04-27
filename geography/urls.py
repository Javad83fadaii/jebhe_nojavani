from django.urls import include, path
from rest_framework.routers import DefaultRouter

from geography.views import MosqueViewSet, SchoolViewSet

router = DefaultRouter()
router.register(r"schools", SchoolViewSet, basename="schools")
router.register(r"mosques", MosqueViewSet, basename="mosques")

urlpatterns = [
    path("", include(router.urls)),
]
