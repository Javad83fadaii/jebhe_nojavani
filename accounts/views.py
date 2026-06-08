from __future__ import annotations

from datetime import timedelta
import logging
from secrets import randbelow

from django.contrib.auth import login as auth_login
from django.utils import timezone
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import PasswordResetRequest, Seller, User
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
from accounts.services.sms import send_password_reset_code

PASSWORD_RESET_CODE_TTL_SECONDS = 2 * 60
logger = logging.getLogger(__name__)


def _get_client_ip(request) -> str | None:
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR") or None


def _mask_phone_number(phone_number: str) -> str:
    normalized = str(phone_number or "").strip()
    if len(normalized) < 4:
        return normalized
    return f"{normalized[:3]}****{normalized[-4:]}"


def _extract_provider_error(raw: dict | None) -> str:
    if not isinstance(raw, dict):
        return ""

    direct_error = raw.get("error")
    if direct_error:
        return str(direct_error).strip()

    status_code = raw.get("status")
    message = raw.get("message")
    try:
        if message and int(status_code) != 1:
            return str(message).strip()
    except (TypeError, ValueError):
        if message:
            return str(message).strip()

    return_section = raw.get("return")
    if isinstance(return_section, dict):
        message = return_section.get("message")
        status_code = return_section.get("status")
        if message and str(status_code or "") != "200":
            return str(message).strip()

    return ""


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
        now = timezone.now()

        active_request = (
            PasswordResetRequest.objects.filter(phone_number=phone_number, expires_at__gt=now)
            .order_by("-requested_at")
            .first()
        )
        if active_request:
            retry_after = int(max((active_request.expires_at - now).total_seconds(), 0))
            return Response(
                {
                    "detail": "برای دریافت کد جدید باید کمی صبر کنید.",
                    "retry_after_seconds": retry_after,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        verification_code = f"{100000 + randbelow(900000)}"
        expires_at = now + timedelta(seconds=PASSWORD_RESET_CODE_TTL_SECONDS)

        user = User.objects.filter(phone_number=phone_number).first()
        reset_request = PasswordResetRequest(
            user=user,
            phone_number=phone_number,
            requested_at=now,
            expires_at=expires_at,
            ip_address=_get_client_ip(request),
            user_agent=str(request.META.get("HTTP_USER_AGENT") or "")[:2048],
        )
        reset_request.set_code(verification_code)
        reset_request.save()

        try:
            sms_result = send_password_reset_code(phone_number=phone_number, code=verification_code)
            reset_request.provider = sms_result.provider
            reset_request.send_attempted_at = timezone.now()
            reset_request.provider_message_id = sms_result.message_id
            reset_request.provider_response = sms_result.raw
        except Exception as exc:
            logger.exception(
                "Password reset SMS send crashed",
                extra={
                    "phone_number_masked": _mask_phone_number(phone_number),
                    "request_id": reset_request.pk,
                    "client_ip": reset_request.ip_address,
                },
            )
            reset_request.status = PasswordResetRequest.Status.FAILED
            reset_request.provider = "unknown"
            reset_request.send_attempted_at = timezone.now()
            reset_request.send_error = str(exc).strip()
            reset_request.provider_response = {
                "ok": False,
                "error": str(exc).strip(),
                "error_type": exc.__class__.__name__,
            }
            reset_request.save(
                update_fields=[
                    "status",
                    "provider",
                    "provider_response",
                    "send_error",
                    "send_attempted_at",
                    "updated_at",
                ]
            )
            return Response(
                {"detail": "سرویس پیامک در دسترس نیست. دوباره تلاش کنید."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not sms_result.ok:
            provider_error = _extract_provider_error(sms_result.raw) or "ارسال پیامک ناموفق بود."
            logger.warning(
                "Password reset SMS send returned unsuccessful result",
                extra={
                    "phone_number_masked": _mask_phone_number(phone_number),
                    "request_id": reset_request.pk,
                    "provider": sms_result.provider,
                    "provider_message_id": sms_result.message_id,
                    "provider_error": provider_error,
                    "provider_response": sms_result.raw,
                },
            )
            reset_request.status = PasswordResetRequest.Status.FAILED
            reset_request.send_error = provider_error
            reset_request.save(
                update_fields=[
                    "status",
                    "provider",
                    "provider_message_id",
                    "provider_response",
                    "send_error",
                    "send_attempted_at",
                    "updated_at",
                ]
            )
            return Response(
                {"detail": "ارسال پیامک ناموفق بود. دوباره تلاش کنید."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        reset_request.save(
            update_fields=[
                "provider",
                "provider_message_id",
                "provider_response",
                "send_error",
                "send_attempted_at",
                "updated_at",
            ]
        )

        confirm_url = f"{reverse('password_reset_confirm')}?phone={phone_number}"
        return Response(
            {
                "detail": "کد بازیابی ارسال شد.",
                "phone_number": phone_number,
                "expires_in_seconds": PASSWORD_RESET_CODE_TTL_SECONDS,
                "redirect_url": confirm_url,
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        verification_code = serializer.validated_data["code"]

        reset_request = (
            PasswordResetRequest.objects.filter(phone_number=phone_number).order_by("-requested_at").first()
        )
        if not reset_request or reset_request.is_expired or reset_request.status != PasswordResetRequest.Status.PENDING:
            return Response(
                {"detail": "درخواست بازیابی معتبر نیست یا زمان آن منقضی شده است. دوباره تلاش کنید."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not reset_request.check_code(verification_code):
            return Response(
                {"code": ["کد تایید وارد شده صحیح نیست."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.get(phone_number=phone_number)
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        reset_request.status = PasswordResetRequest.Status.USED
        reset_request.used_at = timezone.now()
        reset_request.save(update_fields=["status", "used_at", "updated_at"])

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
