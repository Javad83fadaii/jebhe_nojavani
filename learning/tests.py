from django.test import TestCase

from accounts.models import Rank, User
from learning.models import (
    LearningPath,
    LearningStage,
    StageQuestion,
    StageQuestionSet,
    UserLearningProgress,
    UserStageExam,
    UserStageProgress,
)


class LearningPathAccessTestCase(TestCase):
    def setUp(self):
        Rank.ensure_default_ranks()
        self.rank_afsar_5 = Rank.objects.get(level=2)
        self.learning_path = LearningPath.objects.create(
            rank=self.rank_afsar_5,
            title="سیر افسر 5",
            publish_status=LearningPath.PublishStatus.PUBLISHED,
        )
        self.user = User.objects.create_user(
            phone_number="09129999999",
            password="StrongPass123!",
            first_name="کاربر",
            last_name="آزمایشی",
        )

    def test_learning_path_stays_locked_below_rank_threshold(self):
        self.user.total_points = 100
        self.user.save(update_fields=["total_points", "current_rank", "updated_at"])

        self.assertEqual(self.rank_afsar_5.get_unlock_points(), 1000)
        self.assertFalse(self.learning_path.can_user_access(self.user))

    def test_learning_path_unlocks_at_rank_threshold(self):
        self.user.total_points = 1000
        self.user.save(update_fields=["total_points", "current_rank", "updated_at"])

        self.assertTrue(self.learning_path.can_user_access(self.user))


class LearningProgressFlowTestCase(TestCase):
    def setUp(self):
        Rank.ensure_default_ranks()
        self.rank_afsar_6 = Rank.objects.get(level=1)
        self.user = User.objects.create_user(
            phone_number="09121111111",
            password="StrongPass123!",
            first_name="مسیر",
            last_name="آزمایشی",
        )
        self.learning_path = LearningPath.objects.create(
            rank=self.rank_afsar_6,
            title="سیر افسر 6",
            publish_status=LearningPath.PublishStatus.PUBLISHED,
        )
        self.stages = [
            LearningStage.objects.create(
                learning_path=self.learning_path,
                title=f"مرحله {index}",
                stage_number=index,
                content_type=LearningStage.ContentType.ARTICLE,
            )
            for index in range(1, 11)
        ]

    def test_stage_points_and_required_points_are_normalized(self):
        stage_1 = self.stages[0]
        stage_6 = self.stages[5]

        self.assertEqual(stage_1.stage_points, 10)
        self.assertEqual(stage_1.required_points, 0)
        self.assertEqual(stage_6.stage_points, 10)
        self.assertEqual(stage_6.required_points, 50)

    def test_progress_unlocks_only_the_next_stage_in_order(self):
        user_progress = self.user.enroll_in_path(self.learning_path)

        for stage in self.stages[:5]:
            stage_progress = UserStageProgress.objects.get(
                user_learning_progress=user_progress,
                learning_stage=stage,
            )
            stage_progress.pass_stage(20)

        user_progress.refresh_from_db()
        self.user.refresh_from_db()
        stage_6_progress = UserStageProgress.objects.get(
            user_learning_progress=user_progress,
            learning_stage=self.stages[5],
        )
        stage_7_progress = UserStageProgress.objects.get(
            user_learning_progress=user_progress,
            learning_stage=self.stages[6],
        )

        self.assertEqual(user_progress.completed_stages_count, 5)
        self.assertEqual(user_progress.total_score, 50)
        self.assertEqual(user_progress.current_stage_id, self.stages[5].id)
        self.assertEqual(self.user.total_points, 50)
        self.assertEqual(stage_6_progress.status, UserStageProgress.StageStatus.UNLOCKED)
        self.assertEqual(stage_7_progress.status, UserStageProgress.StageStatus.LOCKED)

    def test_passing_stage_exam_awards_points_and_unlocks_next_stage(self):
        user_progress = self.user.enroll_in_path(self.learning_path)
        stage_1_progress = UserStageProgress.objects.get(
            user_learning_progress=user_progress,
            learning_stage=self.stages[0],
        )
        question_set = StageQuestionSet.objects.create(
            learning_stage=self.stages[0],
            set_number=1,
            title="نمونه سوال مرحله 1",
        )
        question = StageQuestion.objects.create(
            question_set=question_set,
            text="پایتخت ایران چیست؟",
            question_number=1,
            question_type=StageQuestion.QuestionType.MULTIPLE_CHOICE,
            option1="تهران",
            option2="قم",
            option3="اصفهان",
            option4="شیراز",
            correct_answer="تهران",
            question_points=20,
        )

        exam = stage_1_progress.start_exam(question_set)
        exam.submit_answer(question, "تهران")
        exam.finish_exam()

        exam.refresh_from_db()
        user_progress.refresh_from_db()
        stage_1_progress.refresh_from_db()
        self.user.refresh_from_db()
        stage_2_progress = UserStageProgress.objects.get(
            user_learning_progress=user_progress,
            learning_stage=self.stages[1],
        )
        stage_3_progress = UserStageProgress.objects.get(
            user_learning_progress=user_progress,
            learning_stage=self.stages[2],
        )

        self.assertEqual(exam.status, UserStageExam.ExamStatus.PASSED)
        self.assertEqual(stage_1_progress.status, UserStageProgress.StageStatus.PASSED)
        self.assertEqual(stage_1_progress.score_earned, 10)
        self.assertEqual(user_progress.total_score, 10)
        self.assertEqual(user_progress.completed_stages_count, 1)
        self.assertEqual(self.user.total_points, 10)
        self.assertEqual(stage_2_progress.status, UserStageProgress.StageStatus.UNLOCKED)
        self.assertEqual(stage_3_progress.status, UserStageProgress.StageStatus.LOCKED)
