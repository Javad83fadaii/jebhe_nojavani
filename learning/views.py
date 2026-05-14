from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView, View

from accounts.models import Rank
from learning.models import (
    LearningPath,
    LearningStage,
    StageQuestionSet,
    UserExamAnswer,
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


class LearningPathStagesView(LoginRequiredMixin, DetailView):
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
        learning_path = self.get_object()
        if not learning_path.can_user_access(request.user):
            return _redirect_for_locked_path(request, learning_path)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        learning_path = self.get_object()
        learning_path.sync_totals()
        context["stages"] = learning_path.get_active_stages()
        context["user_progress"] = None
        context["user_stage_progresses_map"] = {}
        context["required_points"] = learning_path.get_unlock_points()

        if self.request.user.is_authenticated:
            user_progress = UserLearningProgress.objects.filter(
                user=self.request.user, learning_path=learning_path
            ).first()
            context["user_progress"] = user_progress

            if user_progress:
                user_progress.sync_stage_progresses()
                user_stage_progresses = UserStageProgress.objects.filter(
                    user_learning_progress=user_progress
                ).select_related("learning_stage")

                context["user_stage_progresses_map"] = {
                    usp.learning_stage.pk: usp for usp in user_stage_progresses
                }

        return context


@login_required
def enroll_in_learning_path(request, pk):
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


class UserLearningProgressDetailView(LoginRequiredMixin, DetailView):
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


class LearningStageDetailView(LoginRequiredMixin, DetailView):
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

        if user.is_authenticated:
            user_progress = UserLearningProgress.objects.filter(
                user=user,
                learning_path=learning_stage.learning_path,
            ).first()
            if user_progress:
                user_progress.sync_stage_progresses()
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


class LearningStageQuestionsView(LoginRequiredMixin, DetailView):
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
            user_progress.sync_stage_progresses()
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
        if active_exam:
            messages.warning(request, "شما در حال حاضر یک آزمون فعال برای این مرحله دارید.")
            return redirect("learning:take_exam", pk=active_exam.pk)

        new_exam = user_stage_progress.start_exam(question_set)
        return redirect("learning:take_exam", pk=new_exam.pk)

    messages.error(request, "درخواست نامعتبر.")
    return redirect("learning:learning_stage_detail", pk=user_stage_progress.learning_stage.pk)


class TakeExamView(LoginRequiredMixin, DetailView):
    login_url = reverse_lazy("index")
    redirect_field_name = None
    model = UserStageExam
    template_name = "learning/take_exam.html"
    context_object_name = "exam"

    def get_queryset(self):
        # Ensure only the current user's active exam can be viewed
        return UserStageExam.objects.filter(
            user=self.request.user,
            status=UserStageExam.ExamStatus.IN_PROGRESS,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exam = self.get_object()
        context["questions"] = exam.question_set.questions.order_by("question_number")
        context["user_answers"] = {
            ans.question.pk: ans.user_answer for ans in exam.answers.all()
        }
        return context


@login_required
def submit_answer(request, exam_pk, question_pk):
    exam = get_object_or_404(
        UserStageExam,
        pk=exam_pk,
        user=request.user,
        status=UserStageExam.ExamStatus.IN_PROGRESS,
    )
    question = get_object_or_404(exam.question_set.questions, pk=question_pk)

    if request.method == "POST":
        user_answer_text = request.POST.get("answer")
        if not user_answer_text:
            messages.error(request, "لطفاً یک پاسخ وارد کنید.")
            return redirect("learning:take_exam", pk=exam.pk)

        # Call the submit_answer method on the exam instance
        exam.submit_answer(question, user_answer_text)
        messages.success(request, "پاسخ شما با موفقیت ثبت شد.")
        return redirect("learning:take_exam", pk=exam.pk)

    messages.error(request, "درخواست نامعتبر.")
    return redirect("learning:take_exam", pk=exam.pk)


@login_required
def finish_exam(request, pk):
    exam = get_object_or_404(
        UserStageExam,
        pk=pk,
        user=request.user,
        status=UserStageExam.ExamStatus.IN_PROGRESS,
    )

    if request.method == "POST":
        exam.finish_exam()
        if exam.status == UserStageExam.ExamStatus.PASSED:
            messages.success(request, f"تبریک! شما آزمون مرحله {exam.user_stage_progress.learning_stage.title} را با موفقیت پشت سر گذاشتید.")
        else:
            messages.error(request, f"متاسفانه شما در آزمون مرحله {exam.user_stage_progress.learning_stage.title} مردود شدید. لطفا مجددا مطالعه کرده و تلاش کنید.")
        return redirect("learning:user_learning_progress_detail", pk=exam.user_stage_progress.user_learning_progress.pk)

    messages.error(request, "درخواست نامعتبر.")
    return redirect("learning:take_exam", pk=exam.pk)


class RankCardsView(LoginRequiredMixin, ListView):
    login_url = reverse_lazy("index")
    redirect_field_name = None
    model = Rank
    template_name = "learning/rank_cards.html"
    context_object_name = "ranks"
    queryset = Rank.objects.all().order_by("min_points", "level")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        user_points = user.total_points if user.is_authenticated else 0
        ranks = list(context["ranks"])
        user_current_rank = _get_active_rank_for_points(user_points, ranks)

        context["user_current_rank"] = user_current_rank
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

            learning_path = rank.learning_paths.filter(
                publish_status=LearningPath.PublishStatus.PUBLISHED
            ).order_by("display_order", "title").first()

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
