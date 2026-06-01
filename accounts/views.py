from __future__ import annotations

import time
from secrets import randbelow

from django.contrib.auth import login as auth_login
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Seller, User
from accounts.serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    SellerLoginSerializer,
    SellerProfileSerializer,
    SellerRegistrationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)

PASSWORD_RESET_SESSION_KEY = "password_reset_flow"
PASSWORD_RESET_CODE_TTL_SECONDS = 5 * 60


def _clear_password_reset_session(request) -> None:
    if PASSWORD_RESET_SESSION_KEY in request.session:
        del request.session[PASSWORD_RESET_SESSION_KEY]
        request.session.modified = True


def _get_password_reset_session(request):
    session_data = request.session.get(PASSWORD_RESET_SESSION_KEY) or {}
    requested_at = float(session_data.get("requested_at") or 0)
    is_expired = (time.time() - requested_at) > PASSWORD_RESET_CODE_TTL_SECONDS
    if session_data and is_expired:
        _clear_password_reset_session(request)
        return None
    return session_data or None


class UserRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # پراپرتی is_seller قابل ذخیره در دیتابیس نیست، بنابراین حذف شد
        user = serializer.save()
        auth_login(request, user)

        refresh = RefreshToken.for_user(user)
        return Response(
            {"refresh": str(refresh), "access": str(refresh.access_token)},
            status=status.HTTP_201_CREATED,
        )


class UserLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user_type = serializer.validated_data.get("user_type", "user")
        auth_login(request, user)

        refresh = RefreshToken.for_user(user)
        next_url = request.data.get("next") or request.query_params.get("next") or ""
        if user_type == "seller":
            redirect_url = reverse("bazar:seller-dashboard")
        elif next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            redirect_url = next_url
        else:
            redirect_url = reverse("home")
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user_type": user_type,
                "redirect_url": redirect_url,
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        verification_code = f"{100000 + randbelow(900000)}"
        request.session[PASSWORD_RESET_SESSION_KEY] = {
            "phone_number": phone_number,
            "code": verification_code,
            "requested_at": time.time(),
        }
        request.session.modified = True

        confirm_url = f"{reverse('password_reset_confirm')}?phone={phone_number}"
        return Response(
            {
                "detail": "کد بازیابی موقت ایجاد شد. بعداً این کد از طریق پنل پیامکی برای کاربر ارسال می‌شود.",
                "phone_number": phone_number,
                "development_code": verification_code,
                "expires_in_seconds": PASSWORD_RESET_CODE_TTL_SECONDS,
                "sms_provider_connected": False,
                "redirect_url": confirm_url,
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_data = _get_password_reset_session(request)
        if not session_data:
            return Response(
                {"detail": "درخواست بازیابی معتبر نیست یا زمان آن منقضی شده است. دوباره تلاش کنید."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        phone_number = serializer.validated_data["phone_number"]
        verification_code = serializer.validated_data["code"]

        if session_data.get("phone_number") != phone_number:
            return Response(
                {"phone_number": ["شماره تلفن با درخواست بازیابی ثبت‌شده مطابقت ندارد."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if session_data.get("code") != verification_code:
            return Response(
                {"code": ["کد تایید وارد شده صحیح نیست."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.get(phone_number=phone_number)
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        _clear_password_reset_session(request)

        auth_login(request, user)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "detail": "رمز عبور با موفقیت تغییر کرد و وارد حساب کاربری شدید.",
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user_type": "seller" if user.is_seller else "user",
                "redirect_url": reverse("bazar:seller-dashboard") if user.is_seller else reverse("home"),
            },
            status=status.HTTP_200_OK,
        )


class UserProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer

    def get_queryset(self):
        return super().get_queryset().filter(pk=self.request.user.pk)

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        if request.method.lower() == "get":
            serializer = self.get_serializer(request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class SellerRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SellerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"detail": "ثبت‌نام با موفقیت انجام شد. پس از تایید حساب، می‌توانید وارد شوید."},
            status=status.HTTP_201_CREATED,
        )


class SellerLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SellerLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        auth_login(request, user)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user_type": "seller",
                "redirect_url": reverse("bazar:seller-dashboard"),
            },
            status=status.HTTP_200_OK,
        )


class SellerProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Seller.objects.select_related("user")
    serializer_class = SellerProfileSerializer

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        if not request.user.is_seller:
            return Response({"detail": "پروفایل فروشنده یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        seller_profile = request.user.seller_profile

        if request.method.lower() == "get":
            serializer = self.get_serializer(seller_profile)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(seller_profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
