from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView, View

from learning.models import (
    LearningPath,
    LearningStage,
    UserExamAnswer,
    UserLearningProgress,
    UserStageExam,
    UserStageProgress,
)


class LearningPathListView(ListView):
    model = LearningPath
    template_name = "learning/learning_path_list.html"
    context_object_name = "learning_paths"
    queryset = LearningPath.objects.filter(publish_status=LearningPath.PublishStatus.PUBLISHED).order_by(
        "display_order"
    )


class LearningPathDetailView(DetailView):
    model = LearningPath
    template_name = "learning/learning_path_detail.html"
    context_object_name = "learning_path"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        learning_path = self.get_object()
        context["user_progress"] = None
        context["user_stage_progresses_map"] = {} # Map stage_pk to user_stage_progress object

        if self.request.user.is_authenticated:
            user_progress = UserLearningProgress.objects.filter(
                user=self.request.user, learning_path=learning_path
            ).first()
            context["user_progress"] = user_progress

            if user_progress:
                user_stage_progresses = UserStageProgress.objects.filter(
                    user_learning_progress=user_progress
                ).select_related('learning_stage') # Eager load related stage
                
                # Create a map for quick lookup
                context["user_stage_progresses_map"] = {
                    usp.learning_stage.pk: usp for usp in user_stage_progresses
                }

        return context


@login_required
def enroll_in_learning_path(request, pk):
    learning_path = get_object_or_404(LearningPath, pk=pk)
    user = request.user

    if request.method == "POST":
        user_progress = user.enroll_in_path(learning_path)
        messages.success(request, f"شما با موفقیت در سیر مطالعاتی {learning_path.title} ثبت‌نام کردید.")
        return redirect("learning:user_learning_progress_detail", pk=user_progress.pk)

    messages.error(request, "درخواست نامعتبر.")
    return redirect("learning:learning_path_detail", pk=pk)


class UserLearningProgressDetailView(DetailView):
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


class LearningStageDetailView(DetailView):
    model = LearningStage
    template_name = "learning/learning_stage_detail.html"
    context_object_name = "learning_stage"

    def get_queryset(self):
        # Ensure the stage belongs to a published learning path
        return LearningStage.objects.filter(learning_path__publish_status=LearningPath.PublishStatus.PUBLISHED)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        learning_stage = self.get_object()
        user = self.request.user

        if user.is_authenticated:
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


class TakeExamView(DetailView):
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
