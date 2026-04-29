from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'active', views.ChallengeViewSet, basename='challenge-active')
router.register(r'participations', views.ParticipationViewSet, basename='challenge-participation')

urlpatterns = [
    path('api/', include(router.urls)),
]
