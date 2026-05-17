from django.urls import include, path
from rest_framework.routers import DefaultRouter

from geography.views import CityListView, MosqueViewSet, ProvinceListView, SchoolViewSet

router = DefaultRouter()
router.register(r"schools", SchoolViewSet, basename="schools")
router.register(r"mosques", MosqueViewSet, basename="mosques")

urlpatterns = [
    path("provinces/", ProvinceListView.as_view(), name="province-list"),
    path("cities/", CityListView.as_view(), name="city-list"),
    path("", include(router.urls)),
]
