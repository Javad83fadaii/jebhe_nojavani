from django.contrib.auth import logout as auth_logout
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render

from learning.models import LearningPath, LearningStage
from challenges.models import Challenge, ChallengeParticipation
from django.utils import timezone


def _redirect_guest_to_index(request):
    if not request.user.is_authenticated:
        return redirect("index")
    return None

def home(request):
    """
    نمایش صفحه خانه برای کاربران وارد شده
    """
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect

    return render(
        request,
        "home.html",
        {
            "page_name": "home",
            "page_title": "جبهه نوجوانی | شروع تغییر",
        },
    )


def challenges(request):
    """
    نمایش لیست چالش‌های فعال برای کاربر
    """
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect

    now = timezone.now()
    active_challenges = Challenge.objects.filter(
        is_active=True,
        start_date__lte=now,
        end_date__gte=now
    )
    
    user_participations = []
    if request.user.is_authenticated:
        user_participations = ChallengeParticipation.objects.filter(
            user=request.user
        ).values_list('challenge_id', flat=True)

    return render(
        request,
        "challenges.html",
        {
            "page_name": "challenges",
            "page_title": "چالش‌ها | جبهه نوجوانی",
            "active_challenges": active_challenges,
            "user_participations": user_participations,
        },
    )


def challenge_detail(request, pk):
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect

    challenge = get_object_or_404(LearningPath, pk=pk, publish_status=LearningPath.PublishStatus.PUBLISHED)
    return render(
        request,
        "challenge_detail.html",
        {
            "page_name": "challenges",
            "page_title": f"جزئیات چالش {challenge.title} | جبهه نوجوانی",
            "challenge": challenge,
        },
    )


def shop(request):
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect

    return render(
        request,
        "shop.html",
        {
            "page_name": "shop",
            "page_title": "فروشگاه | جبهه نوجوانی",
        },
    )


def profile(request):
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect

    return render(
        request,
        "profile.html",
        {
            "page_name": "profile",
            "page_title": "پروفایل | جبهه نوجوانی",
        },
    )


def login(request):
    if request.user.is_authenticated:
        return redirect("home")

    return render(
        request,
        "login.html",
        {
            "page_name": "login",
            "page_title": "ورود | جبهه نوجوانی",
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    return render(
        request,
        "register.html",
        {
            "page_name": "register",
            "page_title": "ثبت‌نام | جبهه نوجوانی",
        },
    )


def profile_edit(request):
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect

    return render(
        request,
        "profile_edit.html",
        {
            "page_name": "profile",
            "page_title": "ویرایش پروفایل | جبهه نوجوانی",
        },
    )


def seller_register(request):
    if request.user.is_authenticated:
        return redirect("home")

    return render(
        request,
        "seller-register.html",
        {
            "page_name": "seller-register",
            "page_title": "ثبت‌نام فروشنده | جبهه نوجوانی",
        },
    )


def seller_login(request):
    if request.user.is_authenticated:
        return redirect("home")

    return render(
        request,
        "seller-login.html",
        {
            "page_name": "seller-login",
            "page_title": "ورود فروشنده | جبهه نوجوانی",
        },
    )


def seller_profile(request):
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect

    return render(
        request,
        "seller-profile.html",
        {
            "page_name": "seller-profile",
            "page_title": "پروفایل فروشنده | جبهه نوجوانی",
        },
    )

def index_view(request):
    """
    نمایش صفحه اصلی (Landing Page) برای کاربران مهمان
    و انتقال به صفحه خانه برای کاربران وارد شده
    """
    if request.user.is_authenticated:
        return redirect("home")
        
    context = {
        'page_title': 'جبهه نوجوانی | صفحه اصلی',
        'page_name': 'index'
    }
    return render(request, 'index.html', context)


def logout_view(request):
    """
    خروج از حساب کاربری و بازگشت به صفحه اصلی
    """
    auth_logout(request)
    return redirect("/?logout=true")
