from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout as auth_logout
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import Rank
from learning.models import LearningPath, LearningStage
from challenges.models import Challenge, ChallengeParticipation
from django.utils import timezone


def _group_user_challenge_participations(user):
    participations = (
        ChallengeParticipation.objects.filter(user=user)
        .select_related("challenge")
        .order_by("-participated_at")
    )

    active_participations = []
    pending_participations = []
    past_participations = []
    for participation in participations:
        if participation.status == ChallengeParticipation.Status.SUBMITTED:
            pending_participations.append(participation)
            continue
        if participation.challenge.is_currently_active:
            active_participations.append(participation)
        else:
            past_participations.append(participation)

    return active_participations, pending_participations, past_participations


def _redirect_guest_to_index(request):
    if not request.user.is_authenticated:
        return redirect("index")
    return None


def _redirect_seller_to_panel(request):
    if request.user.is_authenticated and request.user.is_seller and not request.session.get("seller_site_view", False):
        return redirect("bazar:seller-dashboard")
    return None


def home(request):
    """
    نمایش صفحه خانه برای کاربران وارد شده
    """
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect

    user = request.user

    # محاسبه رتبه کاربر در کل سیستم
    user_rank = 0
    leaderboard = None
    if user.is_authenticated:
        # دریافت جدول رده‌بندی (۱۰ نفر برتر)
        leaderboard = (
            user.__class__.objects.filter(is_active=True)
            .order_by("-total_points", "-date_joined")
            .select_related("current_rank")
        )[:10]

        # محاسبه رتبه کاربر
        for idx, u in enumerate(leaderboard, 1):
            if u.id == user.id:
                user_rank = idx
                break

        # اگر کاربر در ۱۰ نفر برتر نبود، رتبه را محاسبه کنیم
        if user_rank == 0:
            user_rank = (
                user.__class__.objects.filter(
                    is_active=True,
                    total_points__gt=user.total_points
                ).count() + 1
            )

    # تعداد مسابقات/مسیرهای یادگیری که کاربر در آن شرکت کرده
    user_competitions_count = 0
    if user.is_authenticated:
        user_competitions_count = user.learning_progresses.count()

    return render(
        request,
        "home.html",
        {
            "page_name": "home",
            "page_title": "جبهه نوجوانی | شروع تغییر",
            "user": user,
            "leaderboard": leaderboard,
            "user_rank": user_rank,
            "user_competitions_count": user_competitions_count,
        },
    )


def challenges(request):
    """
    نمایش لیست چالش‌های فعال برای کاربر
    """
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect

    now = timezone.now()
    active_challenges = Challenge.objects.filter(
        is_active=True,
        start_date__lte=now,
        end_date__gte=now
    )
    
    user_participations = set()
    active_participations = []
    pending_participations = []
    past_participations = []
    if request.user.is_authenticated:
        user_participations = set(
            ChallengeParticipation.objects.filter(
            user=request.user
            ).values_list('challenge_id', flat=True)
        )
        (
            active_participations,
            pending_participations,
            past_participations,
        ) = _group_user_challenge_participations(request.user)

    return render(
        request,
        "challenges/challenges.html",
        {
            "page_name": "challenges",
            "page_title": "چالش‌ها | جبهه نوجوانی",
            "active_challenges": active_challenges,
            "user_participations": user_participations,
            "active_participations": active_participations,
            "pending_participations": pending_participations,
            "past_participations": past_participations,
        },
    )


def challenge_detail(request, pk):
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect

    challenge = get_object_or_404(Challenge, pk=pk, is_active=True)
    participation = None
    if request.user.is_authenticated:
        participation = ChallengeParticipation.objects.filter(user=request.user, challenge=challenge).first()
    return render(
        request,
        "challenges/challenge_detail.html",
        {
            "page_name": "challenges",
            "page_title": f"جزئیات چالش {challenge.title} | جبهه نوجوانی",
            "challenge": challenge,
            "participation": participation,
        },
    )


def my_challenges(request):
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect

    return redirect("challenges")


def shop(request):
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    return redirect("bazar:product-list")


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
    """
    این ویو حالا یک تمپلیت مشترک (auth.html) با ویو register رندر می‌کند.
    initial_mode مشخص می‌کند که کارت با کدام پنل باز شود.
    """
    if request.user.is_authenticated:
        if request.user.is_seller:
            return redirect("bazar:seller-dashboard")
        return redirect("home")

    return render(
        request,
        "auth.html",
        {
            "page_name": "login",
            "page_title": "ورود | جبهه نوجوانی",
            "initial_mode": "login",
        },
    )


def forgot_password(request):
    if request.user.is_authenticated:
        if request.user.is_seller:
            return redirect("bazar:seller-dashboard")
        return redirect("home")

    return render(
        request,
        "forgot_password.html",
        {
            "page_name": "forgot-password",
            "page_title": "بازیابی رمز عبور | جبهه نوجوانی",
        },
    )


def password_reset_confirm(request):
    if request.user.is_authenticated:
        if request.user.is_seller:
            return redirect("bazar:seller-dashboard")
        return redirect("home")

    return render(
        request,
        "reset_password_confirm.html",
        {
            "page_name": "password-reset-confirm",
            "page_title": "تعیین رمز عبور جدید | جبهه نوجوانی",
        },
    )


def register(request):
    """
    این ویو هم همان تمپلیت مشترک auth.html را با initial_mode='register' رندر می‌کند.
    """
    if request.user.is_authenticated:
        return redirect("home")

    return render(
        request,
        "auth.html",
        {
            "page_name": "register",
            "page_title": "ثبت‌نام | جبهه نوجوانی",
            "initial_mode": "register",
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

    return redirect(f"{reverse('login')}?next={reverse('bazar:seller-dashboard')}")


def seller_profile(request):
    guest_redirect = _redirect_guest_to_index(request)
    if guest_redirect:
        return guest_redirect
    return redirect("profile")


@login_required
def seller_view_site(request):
    if request.user.is_seller:
        request.session["seller_site_view"] = True
        request.session.modified = True
    return redirect("home")


@login_required
def seller_view_panel(request):
    if request.user.is_seller:
        request.session["seller_site_view"] = False
        request.session.modified = True
    return redirect("bazar:seller-dashboard")


def index_view(request):
    """
    نمایش صفحه اصلی (Landing Page) برای کاربران مهمان
    و انتقال به صفحه خانه برای کاربران وارد شده
    """
    if request.user.is_authenticated:
        if request.user.is_seller and not request.session.get("seller_site_view", False):
            return redirect("bazar:seller-dashboard")
        return redirect("home")
        
    context = {
        'page_title': 'جبهه نوجوانی | صفحه اصلی',
        'page_name': 'index',
        'ranks': Rank.objects.order_by('level'),
    }
    return render(request, 'index.html', context)


def logout_view(request):
    """
    خروج از حساب کاربری و بازگشت به صفحه اصلی
    """
    auth_logout(request)
    return redirect("/?logout=true")


@login_required
def user_progress_api(request):
    total_points = int(getattr(request.user, "total_points", 0) or 0)
    progress_metrics = Rank.get_progress_metrics(total_points)
    current_rank = progress_metrics["current_rank"]

    return JsonResponse(
        {
            "total_points": total_points,
            "points_per_level": progress_metrics["points_per_level"],
            "level_points": progress_metrics["level_points"],
            "level_number": progress_metrics["level_number"],
            "level_progress_percent": progress_metrics["level_progress_percent"],
            "current_rank": getattr(current_rank, "name", None),
        }
    )
