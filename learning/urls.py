from django.urls import path

from learning.views import (
    LearningPathDetailView,
    LearningPathListView,
    LearningStageDetailView,
    TakeExamView,
    UserLearningProgressDetailView,
    complete_study,
    enroll_in_learning_path,
    finish_exam,
    start_exam,
    submit_answer,
)

app_name = "learning"

urlpatterns = [
    path("paths/", LearningPathListView.as_view(), name="learning_path_list"),
    path("paths/<int:pk>/", LearningPathDetailView.as_view(), name="learning_path_detail"),
    path("paths/<int:pk>/enroll/", enroll_in_learning_path, name="enroll_in_learning_path"),
    path(
        "progress/<int:pk>/",
        UserLearningProgressDetailView.as_view(),
        name="user_learning_progress_detail",
    ),
    path("stages/<int:pk>/", LearningStageDetailView.as_view(), name="learning_stage_detail"),
    path("stages/<int:pk>/complete-study/", complete_study, name="complete_study"),
    path("progress/<int:pk>/start-exam/", start_exam, name="start_exam"),
    path("exams/<int:pk>/", TakeExamView.as_view(), name="take_exam"),
    path("exams/<int:exam_pk>/question/<int:question_pk>/submit/", submit_answer, name="submit_answer"),
    path("exams/<int:pk>/finish/", finish_exam, name="finish_exam"),
]
