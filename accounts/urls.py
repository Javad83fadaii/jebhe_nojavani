from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import (
    SellerLoginView,
    SellerProfileViewSet,
    SellerRegistrationView,
    UserLoginView,
    UserProfileViewSet,
    UserRegistrationView,
)

router = DefaultRouter()
router.register(r"profile", UserProfileViewSet, basename="profile")
router.register(r"seller/profile", SellerProfileViewSet, basename="seller-profile")

urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="user-register"),
    path("login/", UserLoginView.as_view(), name="user-login"),
    path("seller/register/", SellerRegistrationView.as_view(), name="seller-register"),
    path("seller/login/", SellerLoginView.as_view(), name="seller-login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("", include(router.urls)),
]
