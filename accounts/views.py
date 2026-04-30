from __future__ import annotations

from django.contrib.auth import login as auth_login
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.serializers import (
    SellerLoginSerializer,
    SellerProfileSerializer,
    SellerRegistrationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)


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
        auth_login(request, user)

        refresh = RefreshToken.for_user(user)
        return Response(
            {"refresh": str(refresh), "access": str(refresh.access_token)},
            status=status.HTTP_200_OK,
        )


class UserProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    # اصلاح شد: فیلتر بر اساس عدم وجود پروفایل فروشنده
    queryset = User.objects.filter(seller_profile__isnull=True)
    serializer_class = UserProfileSerializer

    def get_queryset(self):
        return super().get_queryset().filter(pk=self.request.user.pk)

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        if request.user.is_seller:
            return Response({"detail": "پروفایل کاربر یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

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
            {"detail": "ثبت‌نام شما موفق بود. پس از تایید ادمین می‌توانید وارد شوید."},
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
            {"refresh": str(refresh), "access": str(refresh.access_token)},
            status=status.HTTP_200_OK,
        )


class SellerProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    # اصلاح شد: فیلتر بر اساس وجود پروفایل فروشنده
    queryset = User.objects.filter(seller_profile__isnull=False)
    serializer_class = SellerProfileSerializer

    def get_queryset(self):
        # اصلاح شد: فیلتر بر اساس وجود پروفایل فروشنده
        return super().get_queryset().filter(pk=self.request.user.pk, seller_profile__isnull=False)

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        if not request.user.is_seller:
            return Response({"detail": "پروفایل فروشنده یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        if request.method.lower() == "get":
            serializer = self.get_serializer(request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
