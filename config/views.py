from django.shortcuts import render, get_object_or_404
from learning.models import LearningPath # Import LearningPath model


def home(request):
    return render(
        request,
        "home.html",
        {
            "page_name": "home",
            "page_title": "نقطه | شروع تغییر",
        },
    )


def challenges(request):
    # Fetch all published learning paths
    learning_paths = LearningPath.objects.filter(publish_status=LearningPath.PublishStatus.PUBLISHED).order_by("display_order")

    return render(
        request,
        "challenges.html",
        {
            "page_name": "challenges",
            "page_title": "چالش‌ها | نقطه",
            "learning_paths": learning_paths, # Pass learning paths to the template
        },
    )


def challenge_detail(request, pk):
    challenge = get_object_or_404(LearningPath, pk=pk, publish_status=LearningPath.PublishStatus.PUBLISHED)
    return render(
        request,
        "challenge_detail.html",
        {
            "page_name": "challenges",
            "page_title": f"جزئیات چالش {challenge.title} | نقطه",
            "challenge": challenge,
        },
    )


def shop(request):
    return render(
        request,
        "shop.html",
        {
            "page_name": "shop",
            "page_title": "فروشگاه | نقطه",
        },
    )


def profile(request):
    return render(
        request,
        "profile.html",
        {
            "page_name": "profile",
            "page_title": "پروفایل | نقطه",
        },
    )


def login(request):
    return render(
        request,
        "login.html",
        {
            "page_name": "login",
            "page_title": "ورود | نقطه",
        },
    )


def register(request):
    return render(
        request,
        "register.html",
        {
            "page_name": "register",
            "page_title": "ثبت‌نام | نقطه",
        },
    )


def profile_edit(request):
    return render(
        request,
        "profile_edit.html",
        {
            "page_name": "profile",
            "page_title": "ویرایش پروفایل | نقطه",
        },
    )


def seller_register(request):
    return render(
        request,
        "seller-register.html",
        {
            "page_name": "seller-register",
            "page_title": "ثبت‌نام فروشنده | نقطه",
        },
    )


def seller_login(request):
    return render(
        request,
        "seller-login.html",
        {
            "page_name": "seller-login",
            "page_title": "ورود فروشنده | نقطه",
        },
    )


def seller_profile(request):
    return render(
        request,
        "seller-profile.html",
        {
            "page_name": "seller-profile",
            "page_title": "پروفایل فروشنده | نقطه",
        },
    )
