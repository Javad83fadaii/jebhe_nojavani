from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404

from learning.models import LearningPath, LearningStage
from challenges.models import Challenge, ChallengeParticipation
from django.utils import timezone

def home(request):
    """
    نمایش صفحه خانه برای کاربران وارد شده
    """
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
    return render(
        request,
        "shop.html",
        {
            "page_name": "shop",
            "page_title": "فروشگاه | جبهه نوجوانی",
        },
    )


def profile(request):
    return render(
        request,
        "profile.html",
        {
            "page_name": "profile",
            "page_title": "پروفایل | جبهه نوجوانی",
        },
    )


def login(request):
    return render(
        request,
        "login.html",
        {
            "page_name": "login",
            "page_title": "ورود | جبهه نوجوانی",
        },
    )


def register(request):
    return render(
        request,
        "register.html",
        {
            "page_name": "register",
            "page_title": "ثبت‌نام | جبهه نوجوانی",
        },
    )


def profile_edit(request):
    return render(
        request,
        "profile_edit.html",
        {
            "page_name": "profile",
            "page_title": "ویرایش پروفایل | جبهه نوجوانی",
        },
    )


def seller_register(request):
    return render(
        request,
        "seller-register.html",
        {
            "page_name": "seller-register",
            "page_title": "ثبت‌نام فروشنده | جبهه نوجوانی",
        },
    )


def seller_login(request):
    return render(
        request,
        "seller-login.html",
        {
            "page_name": "seller-login",
            "page_title": "ورود فروشنده | جبهه نوجوانی",
        },
    )


def seller_profile(request):
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
        return home(request)
        
    context = {
        'page_title': 'جبهه نوجوانی | صفحه اصلی',
        'page_name': 'index'
    }
    return render(request, 'index.html', context)
