from django.core.exceptions import ValidationError
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DetailView, ListView, View

from accounts.models import Rank
from config.view_helpers import redirect_seller_to_panel as _redirect_seller_to_panel
from learning.models import (
    LearningPath,
    LearningStage,
    StageQuestionSet,
    UserLearningProgress,
    UserStageExam,
    UserStageProgress,
)


def _redirect_for_locked_path(request, learning_path):
    required_points = learning_path.get_unlock_points()
    messages.error(
        request,
        f"برای ورود به سیر مطالعاتی {learning_path.title} حداقل {required_points} امتیاز نیاز دارید.",
    )
    return redirect("learning:rank_cards")


def _get_active_rank_for_points(points, ranks):
    active_rank = None
    for rank in ranks:
        if rank.is_unlocked_for_points(points):
            active_rank = rank
        else:
            break
    return active_rank


def _redirect_to_exam_progress(exam):
    return redirect(
        "learning:user_learning_progress_detail",
        pk=exam.user_stage_progress.user_learning_progress.pk,
    )


def _ensure_active_exam(request, exam):
    if exam.status != UserStageExam.ExamStatus.IN_PROGRESS:
        messages.error(request, "این آزمون دیگر فعال نیست.")
        return _redirect_to_exam_progress(exam)

    if exam.expire_if_needed():
        messages.error(request, "زمان آزمون به پایان رسید و نتیجه بر اساس پاسخ‌های ذخیره‌شده ثبت شد.")
        return _redirect_to_exam_progress(exam)

    return None


def _save_exam_answers_from_request(exam, post_data):
    questions = list(exam.question_set.questions.order_by("question_number"))
    existing_answers = {
        answer.question_id: answer
        for answer in exam.answers.select_related("question")
    }
    saved_count = 0
    cleared_count = 0

    for question in questions:
        answer_key = f"question_{question.pk}"
        user_answer_text = post_data.get(answer_key)
        user_answer_text = (user_answer_text or "").strip()
        existing_answer = existing_answers.get(question.pk)

        if user_answer_text:
            exam.submit_answer(question, user_answer_text)
            saved_count += 1
            continue

        if existing_answer:
            existing_answer.delete()
            cleared_count += 1

    return saved_count, cleared_count


def _create_exam_for_stage_progress(stage_progress, question_set):
    if not stage_progress.can_take_exam():
        raise ValidationError("شما قادر به شرکت در آزمون این مرحله نیستید.")

    stage_progress.exam_attempts += 1
    stage_progress.last_question_set_used = question_set
    stage_progress.save(update_fields=["exam_attempts", "last_question_set_used", "updated_at"])

    return UserStageExam.objects.create(
        user=stage_progress.user,
        user_stage_progress=stage_progress,
        question_set=question_set,
        attempt_number=stage_progress.exam_attempts,
        status=UserStageExam.ExamStatus.IN_PROGRESS,
    )


class SellerSiteAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        seller_redirect = _redirect_seller_to_panel(request)
        if seller_redirect:
            return seller_redirect
        return super().dispatch(request, *args, **kwargs)


class LearningPathStagesView(SellerSiteAccessMixin, DetailView):
    login_url = reverse_lazy("index")
    redirect_field_name = None
    model = LearningPath
    template_name = "learning/learning_path_stages.html"
    context_object_name = "learning_path"

    def get_queryset(self):
        return LearningPath.objects.filter(
            publish_status=LearningPath.PublishStatus.PUBLISHED
        ).select_related("rank")

    def dispatch(self, request, *args, **kwargs):
        seller_redirect = _redirect_seller_to_panel(request)
        if seller_redirect:
            return seller_redirect
        learning_path = self.get_object()
        if not learning_path.can_user_access(request.user):
            return _redirect_for_locked_path(request, learning_path)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        learning_path = self.get_object()
        context["stages"] = learning_path.get_active_stages()
        context["user_progress"] = None
        context["user_stage_progresses_map"] = {}
        context["required_points"] = learning_path.get_unlock_points()

        if self.request.user.is_authenticated:
            user_progress = UserLearningProgress.objects.filter(
                user=self.request.user, learning_path=learning_path
            ).first()

            if user_progress:
                user_stage_progresses = UserStageProgress.objects.filter(
                    user_learning_progress=user_progress
                ).select_related("learning_stage")

                context["user_stage_progresses_map"] = {
                    usp.learning_stage.pk: usp for usp in user_stage_progresses
                }
            context["user_progress"] = user_progress

        return context


@login_required
def enroll_in_learning_path(request, pk):
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    learning_path = get_object_or_404(
        LearningPath.objects.filter(
            publish_status=LearningPath.PublishStatus.PUBLISHED
        ).select_related("rank"),
        pk=pk,
    )
    user = request.user

    if request.method == "POST":
        if not learning_path.can_user_access(user):
            return _redirect_for_locked_path(request, learning_path)
        user_progress = user.enroll_in_path(learning_path)
        messages.success(request, f"شما با موفقیت در سیر مطالعاتی {learning_path.title} ثبت‌نام کردید.")
        return redirect("learning:user_learning_progress_detail", pk=user_progress.pk)

    messages.error(request, "درخواست نامعتبر.")
    return redirect("learning:learning_path_stages", pk=pk)


class UserLearningProgressDetailView(SellerSiteAccessMixin, DetailView):
    login_url = reverse_lazy("index")
    redirect_field_name = None
    model = UserLearningProgress
    template_name = "learning/user_learning_progress_detail.html"
    context_object_name = "user_learning_progress"

    def get_queryset(self):
        # Ensure only the current user's progress can be viewed
        return UserLearningProgress.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_learning_progress = self.get_object()
        context["learning_path"] = user_learning_progress.learning_path
        context["user_stage_progresses"] = user_learning_progress.stage_progress.select_related(
            "learning_stage"
        ).order_by("learning_stage__stage_number")
        return context


class LearningStageDetailView(SellerSiteAccessMixin, DetailView):
    login_url = reverse_lazy("index")
    redirect_field_name = None
    model = LearningStage
    template_name = "learning/learning_stage_detail.html"
    context_object_name = "learning_stage"

    def get_queryset(self):
        # Ensure the stage belongs to a published learning path
        return LearningStage.objects.filter(
            learning_path__publish_status=LearningPath.PublishStatus.PUBLISHED,
            is_active=True,
        ).select_related("learning_path", "learning_path__rank")

    def dispatch(self, request, *args, **kwargs):
        learning_stage = self.get_object()
        if not learning_stage.learning_path.can_user_access(request.user):
            return _redirect_for_locked_path(request, learning_stage.learning_path)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        learning_stage = self.get_object()
        user = self.request.user
        context["stage_detail_summary"] = learning_stage.get_detail_summary()

        if user.is_authenticated:
            user_progress = UserLearningProgress.objects.filter(
                user=user,
                learning_path=learning_stage.learning_path,
            ).first()
            user_stage_progress = UserStageProgress.objects.filter(
                user=user,
                learning_stage=learning_stage,
            ).first()
            context["user_stage_progress"] = user_stage_progress

            if user_stage_progress:
                # Update status to 'in_study' if it's 'unlocked' and user visits
                if user_stage_progress.status == UserStageProgress.StageStatus.UNLOCKED:
                    user_stage_progress.start_study()

                # Get active exam if any
                context["active_exam"] = user_stage_progress.exams.filter(
                    status=UserStageExam.ExamStatus.IN_PROGRESS
                ).first()

        return context


class LearningStageQuestionsView(SellerSiteAccessMixin, DetailView):
    login_url = reverse_lazy("index")
    redirect_field_name = None
    model = LearningStage
    template_name = "learning/learning_stage_questions.html"
    context_object_name = "learning_stage"

    def get_queryset(self):
        return (
            LearningStage.objects.filter(
                learning_path__publish_status=LearningPath.PublishStatus.PUBLISHED,
                is_active=True,
            )
            .select_related("learning_path", "learning_path__rank")
            .prefetch_related(
                Prefetch(
                    "question_sets",
                    queryset=StageQuestionSet.objects.filter(is_active=True)
                    .prefetch_related("questions")
                    .order_by("set_number"),
                )
            )
        )

    def dispatch(self, request, *args, **kwargs):
        learning_stage = self.get_object()
        if not learning_stage.learning_path.can_user_access(request.user):
            return _redirect_for_locked_path(request, learning_stage.learning_path)

        user_progress = UserLearningProgress.objects.filter(
            user=request.user,
            learning_path=learning_stage.learning_path,
        ).first()
        if not user_progress:
            return redirect("learning:learning_path_stages", pk=learning_stage.learning_path.pk)

        user_stage_progress = UserStageProgress.objects.filter(
            user=request.user,
            learning_stage=learning_stage,
        ).first()
        if (
            not user_stage_progress
            or user_stage_progress.status == UserStageProgress.StageStatus.LOCKED
        ):
            return redirect("learning:learning_path_stages", pk=learning_stage.learning_path.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        learning_stage = self.get_object()
        user_progress = UserLearningProgress.objects.filter(
            user=self.request.user,
            learning_path=learning_stage.learning_path,
        ).first()
        user_stage_progress = None

        if user_progress:
            user_stage_progress = UserStageProgress.objects.filter(
                user=self.request.user,
                learning_stage=learning_stage,
            ).first()

        question_sets = list(learning_stage.question_sets.all())
        context["user_stage_progress"] = user_stage_progress
        context["question_sets"] = question_sets
        context["question_count"] = sum(
            question_set.questions.count() for question_set in question_sets
        )
        return context


@login_required
def complete_study(request, pk):
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    user_stage_progress = get_object_or_404(
        UserStageProgress,
        pk=pk,
        user=request.user,
    )

    if request.method == "POST":
        if user_stage_progress.status == UserStageProgress.StageStatus.IN_STUDY:
            user_stage_progress.complete_study()
            messages.success(request, "مطالعه این مرحله با موفقیت به اتمام رسید. اکنون می‌توانید در آزمون شرکت کنید.")
        else:
            messages.error(request, "این مرحله در حال مطالعه نیست یا قبلاً به اتمام رسیده است.")

        return redirect("learning:learning_stage_detail", pk=user_stage_progress.learning_stage.pk)

    messages.error(request, "درخواست نامعتبر.")
    return redirect("learning:learning_stage_detail", pk=user_stage_progress.learning_stage.pk)


@login_required
def start_exam(request, pk):
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    user_stage_progress = get_object_or_404(
        UserStageProgress,
        pk=pk,
        user=request.user,
    )

    if request.method == "POST":
        if not user_stage_progress.can_take_exam():
            messages.error(request, "شما قادر به شرکت در آزمون این مرحله نیستید.")
            return redirect("learning:learning_stage_detail", pk=user_stage_progress.learning_stage.pk)

        question_set = user_stage_progress.get_next_question_set()
        if not question_set:
            messages.error(request, "هیچ مجموعه سوالی برای این مرحله یافت نشد.")
            return redirect("learning:learning_stage_detail", pk=user_stage_progress.learning_stage.pk)

        # Ensure no active exam exists for this stage progress
        active_exam = user_stage_progress.exams.filter(status=UserStageExam.ExamStatus.IN_PROGRESS).first()
        if active_exam and active_exam.expire_if_needed():
            active_exam.refresh_from_db()
            user_stage_progress.refresh_from_db()
            if not user_stage_progress.can_take_exam():
                messages.warning(request, "آزمون فعال قبلی منقضی شد و وضعیت مرحله شما به‌روزرسانی شد.")
                return redirect("learning:user_learning_progress_detail", pk=user_stage_progress.user_learning_progress.pk)
            active_exam = None
        if active_exam:
            messages.warning(request, "شما در حال حاضر یک آزمون فعال برای این مرحله دارید.")
            return redirect("learning:take_exam", pk=active_exam.pk)

        new_exam = _create_exam_for_stage_progress(user_stage_progress, question_set)
        return redirect("learning:take_exam", pk=new_exam.pk)

    messages.error(request, "درخواست نامعتبر.")
    return redirect("learning:learning_stage_detail", pk=user_stage_progress.learning_stage.pk)


class TakeExamView(SellerSiteAccessMixin, DetailView):
    login_url = reverse_lazy("index")
    redirect_field_name = None
    model = UserStageExam
    template_name = "learning/take_exam.html"
    context_object_name = "exam"

    def get_queryset(self):
        return UserStageExam.objects.filter(
            user=self.request.user,
        ).select_related("user_stage_progress__learning_stage", "question_set")

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        exam_redirect = _ensure_active_exam(request, self.object)
        if exam_redirect:
            return exam_redirect
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        if hasattr(self, "object"):
            return self.object
        return super().get_object(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exam = self.get_object()
        context["questions"] = exam.question_set.questions.order_by("question_number")
        context["user_answers"] = {
            ans.question.pk: ans.user_answer for ans in exam.answers.all()
        }
        context["remaining_seconds"] = exam.get_remaining_seconds(now=timezone.now())
        context["exam_duration_minutes"] = int(exam.EXAM_DURATION.total_seconds() // 60)
        context["expires_at"] = exam.get_expires_at()
        return context


@login_required
def submit_answer(request, exam_pk, question_pk=None):
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    exam = get_object_or_404(
        UserStageExam,
        pk=exam_pk,
        user=request.user,
    )
    exam_redirect = _ensure_active_exam(request, exam)
    if exam_redirect:
        return exam_redirect

    if question_pk is not None:
        get_object_or_404(exam.question_set.questions, pk=question_pk)

    if request.method == "POST":
        saved_count, cleared_count = _save_exam_answers_from_request(exam, request.POST)
        if saved_count == 0 and cleared_count == 0:
            messages.error(request, "لطفاً حداقل یک پاسخ وارد یا ویرایش کنید.")
            return redirect("learning:take_exam", pk=exam.pk)

        if cleared_count:
            messages.success(request, f"{saved_count} پاسخ ذخیره شد و {cleared_count} پاسخ پاک شد.")
        else:
            messages.success(request, f"{saved_count} پاسخ با موفقیت ذخیره شد.")
        return redirect("learning:take_exam", pk=exam.pk)

    messages.error(request, "درخواست نامعتبر.")
    return redirect("learning:take_exam", pk=exam.pk)


@login_required
def finish_exam(request, pk):
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    exam = get_object_or_404(
        UserStageExam,
        pk=pk,
        user=request.user,
    )
    exam_redirect = _ensure_active_exam(request, exam)
    if exam_redirect:
        return exam_redirect

    if request.method == "POST":
        _save_exam_answers_from_request(exam, request.POST)
        try:
            exam.finish_exam()
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return _redirect_to_exam_progress(exam)
        if exam.status == UserStageExam.ExamStatus.PASSED:
            messages.success(request, f"تبریک! شما آزمون مرحله {exam.user_stage_progress.learning_stage.title} را با موفقیت پشت سر گذاشتید.")
        else:
            messages.error(request, f"متاسفانه شما در آزمون مرحله {exam.user_stage_progress.learning_stage.title} مردود شدید. لطفا مجددا مطالعه کرده و تلاش کنید.")
        return _redirect_to_exam_progress(exam)

    messages.error(request, "درخواست نامعتبر.")
    return redirect("learning:take_exam", pk=exam.pk)


class RankCardsView(SellerSiteAccessMixin, ListView):
    login_url = reverse_lazy("index")
    redirect_field_name = None
    model = Rank
    template_name = "learning/rank_cards.html"
    context_object_name = "ranks"
    def get_queryset(self):
        published_learning_paths = LearningPath.objects.filter(
            publish_status=LearningPath.PublishStatus.PUBLISHED
        ).order_by("display_order", "title")
        return Rank.objects.order_by("min_points", "level").prefetch_related(
            Prefetch("learning_paths", queryset=published_learning_paths, to_attr="published_learning_paths")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        user_points = user.total_points if user.is_authenticated else 0
        ranks = list(context["ranks"])
        current_rank_obj = _get_active_rank_for_points(user_points, ranks)

        context["current_rank_obj"] = current_rank_obj
        context["user_points"] = user_points

        user_progresses = {}
        if user.is_authenticated:
            user_progresses = {
                up.learning_path_id: up
                for up in UserLearningProgress.objects.filter(user=user)
            }

        rank_data = []
        for index, rank in enumerate(ranks):
            next_rank = ranks[index + 1] if index + 1 < len(ranks) else None
            required_points = rank.get_unlock_points()
            next_required_points = next_rank.get_unlock_points() if next_rank else None
            is_unlocked = rank.is_unlocked_for_points(user_points)
            is_completed = next_required_points is not None and user_points >= next_required_points
            is_current = is_unlocked and not is_completed

            progress_percentage = 0
            if is_completed:
                progress_percentage = 100
            elif is_current:
                progress_start = required_points
                progress_end = next_required_points if next_required_points is not None else user_points
                progress_range = max(progress_end - progress_start, 1)
                progress_percentage = min(max(((user_points - progress_start) / progress_range) * 100, 0), 100)

            published_learning_paths = getattr(rank, "published_learning_paths", [])
            learning_path = published_learning_paths[0] if published_learning_paths else None

            user_progress = None
            if learning_path and learning_path.id in user_progresses:
                user_progress = user_progresses[learning_path.id]

            rank_data.append({
                "rank": rank,
                "is_unlocked": is_unlocked,
                "is_locked": not is_unlocked,
                "is_current": is_current,
                "is_completed": is_completed,
                "progress_percentage": progress_percentage,
                "required_points": required_points,
                "next_required_points": next_required_points,
                "points_shortage": max(required_points - user_points, 0),
                "learning_path": learning_path,
                "user_progress": user_progress,
            })

        context["rank_data"] = rank_data
        return context
