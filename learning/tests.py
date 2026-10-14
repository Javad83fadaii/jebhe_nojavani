from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

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

        self.assertEqual(stage_1.stage_points, 100)
        self.assertEqual(stage_1.required_points, 0)
        self.assertEqual(stage_6.stage_points, 100)
        self.assertEqual(stage_6.required_points, 500)

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
        self.assertEqual(user_progress.total_score, 500)
        self.assertEqual(user_progress.current_stage_id, self.stages[5].id)
        self.assertEqual(self.user.total_points, 500)
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
        self.assertEqual(stage_1_progress.score_earned, 100)
        self.assertEqual(user_progress.total_score, 100)
        self.assertEqual(user_progress.completed_stages_count, 1)
        self.assertEqual(self.user.total_points, 100)
        self.assertEqual(stage_2_progress.status, UserStageProgress.StageStatus.UNLOCKED)
        self.assertEqual(stage_3_progress.status, UserStageProgress.StageStatus.LOCKED)

    def test_pass_stage_is_idempotent_for_stale_instances(self):
        user_progress = self.user.enroll_in_path(self.learning_path)
        original_progress = UserStageProgress.objects.get(
            user_learning_progress=user_progress,
            learning_stage=self.stages[0],
        )
        stale_first = UserStageProgress.objects.get(pk=original_progress.pk)
        stale_second = UserStageProgress.objects.get(pk=original_progress.pk)

        stale_first.pass_stage(20)
        stale_second.pass_stage(20)

        original_progress.refresh_from_db()
        user_progress.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(original_progress.status, UserStageProgress.StageStatus.PASSED)
        self.assertEqual(original_progress.score_earned, 100)
        self.assertEqual(user_progress.total_score, 100)
        self.assertEqual(user_progress.completed_stages_count, 1)
        self.assertEqual(self.user.total_points, 100)

    def test_finish_exam_is_protected_against_stale_double_submit(self):
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

        stale_first = UserStageExam.objects.get(pk=exam.pk)
        stale_second = UserStageExam.objects.get(pk=exam.pk)

        stale_first.finish_exam()
        with self.assertRaises(ValidationError):
            stale_second.finish_exam()

        exam.refresh_from_db()
        stage_1_progress.refresh_from_db()
        user_progress.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(exam.status, UserStageExam.ExamStatus.PASSED)
        self.assertEqual(stage_1_progress.status, UserStageProgress.StageStatus.PASSED)
        self.assertEqual(user_progress.total_score, 100)
        self.assertEqual(user_progress.completed_stages_count, 1)
        self.assertEqual(self.user.total_points, 100)

    def test_each_stage_uses_three_random_question_sets_without_repeating_until_all_used(self):
        user_progress = self.user.enroll_in_path(self.learning_path)
        stage_1_progress = UserStageProgress.objects.get(
            user_learning_progress=user_progress,
            learning_stage=self.stages[0],
        )
        question_sets = [
            StageQuestionSet.objects.create(
                learning_stage=self.stages[0],
                set_number=set_number,
                title=f"نمونه سوال {set_number}",
            )
            for set_number in (1, 2, 3)
        ]

        chosen_set_ids = []
        for _ in range(3):
            question_set = stage_1_progress.get_next_question_set()
            self.assertIsNotNone(question_set)
            chosen_set_ids.append(question_set.pk)
            exam = stage_1_progress.start_exam(question_set)
            exam.status = UserStageExam.ExamStatus.FAILED
            exam.save(update_fields=["status", "updated_at"])

        self.assertEqual(len(set(chosen_set_ids)), 3)
        self.assertEqual(set(chosen_set_ids), {qs.pk for qs in question_sets})


class RankCardsViewContextTestCase(TestCase):
    def setUp(self):
        Rank.ensure_default_ranks()
        self.user = User.objects.create_user(
            phone_number="09123332222",
            password="StrongPass123!",
            first_name="درجه",
            last_name="آزمایشی",
        )
        self.user.total_points = 0
        self.user.save(update_fields=["total_points", "updated_at"])

    def test_rank_cards_view_uses_separate_current_rank_object_context_key(self):
        self.client.force_login(self.user)

        response = self.client.get("/learning/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user_current_rank"], "افسر 6")
        self.assertEqual(response.context["current_rank_obj"].name, "افسر 6")


class LearningStageQuestionsAccessTestCase(TestCase):
    def setUp(self):
        Rank.ensure_default_ranks()
        self.rank_afsar_6 = Rank.objects.get(level=1)
        self.user = User.objects.create_user(
            phone_number="09124445555",
            password="StrongPass123!",
            first_name="سوال",
            last_name="آزمایشی",
        )
        self.learning_path = LearningPath.objects.create(
            rank=self.rank_afsar_6,
            title="سیر دسترسی سوالات",
            publish_status=LearningPath.PublishStatus.PUBLISHED,
        )
        self.stage_1 = LearningStage.objects.create(
            learning_path=self.learning_path,
            title="مرحله 1",
            stage_number=1,
            content_type=LearningStage.ContentType.ARTICLE,
        )
        self.stage_2 = LearningStage.objects.create(
            learning_path=self.learning_path,
            title="مرحله 2",
            stage_number=2,
            content_type=LearningStage.ContentType.ARTICLE,
        )

    def test_questions_view_redirects_to_stages_when_user_not_enrolled(self):
        self.client.force_login(self.user)

        response = self.client.get(f"/learning/stages/{self.stage_1.pk}/questions/")

        self.assertRedirects(
            response,
            f"/learning/paths/{self.learning_path.pk}/stages/",
        )

    def test_questions_view_redirects_to_stages_when_stage_is_locked(self):
        self.client.force_login(self.user)
        self.user.enroll_in_path(self.learning_path)

        response = self.client.get(f"/learning/stages/{self.stage_2.pk}/questions/")

        self.assertRedirects(
            response,
            f"/learning/paths/{self.learning_path.pk}/stages/",
        )


class ExamAnswerFlowTestCase(TestCase):
    def setUp(self):
        Rank.ensure_default_ranks()
        self.rank = Rank.objects.get(level=1)
        self.user = User.objects.create_user(
            phone_number="09125556666",
            password="StrongPass123!",
            first_name="آزمون",
            last_name="آزمایشی",
        )
        self.learning_path = LearningPath.objects.create(
            rank=self.rank,
            title="سیر آزمون",
            publish_status=LearningPath.PublishStatus.PUBLISHED,
        )
        self.stage = LearningStage.objects.create(
            learning_path=self.learning_path,
            title="مرحله آزمون",
            stage_number=1,
            content_type=LearningStage.ContentType.ARTICLE,
        )
        self.question_set = StageQuestionSet.objects.create(
            learning_stage=self.stage,
            set_number=1,
            title="نمونه سوال",
        )
        self.stage_progress = UserStageProgress.objects.create(
            user=self.user,
            learning_stage=self.stage,
            user_learning_progress=UserLearningProgress.objects.create(
                user=self.user,
                learning_path=self.learning_path,
                current_stage=self.stage,
            ),
            status=UserStageProgress.StageStatus.READY_FOR_EXAM,
        )

    def test_short_answer_comparison_normalizes_arabic_letters_digits_and_spacing(self):
        question = StageQuestion.objects.create(
            question_set=self.question_set,
            text="کد را وارد کنید",
            question_number=1,
            question_type=StageQuestion.QuestionType.SHORT_ANSWER,
            correct_answer="کد\u200cملی ۱۲۳",
            question_points=20,
        )

        exam = self.stage_progress.start_exam(self.question_set)
        is_correct, score_earned = exam.submit_answer(question, "كد ملي123")

        self.assertTrue(is_correct)
        self.assertEqual(score_earned, 20)

    def test_true_false_answers_accept_persian_values_and_are_canonicalized(self):
        question = StageQuestion.objects.create(
            question_set=self.question_set,
            text="جمله صحیح است؟",
            question_number=1,
            question_type=StageQuestion.QuestionType.TRUE_FALSE,
            correct_answer="صحیح",
            question_points=20,
        )
        question.refresh_from_db()
        exam = self.stage_progress.start_exam(self.question_set)
        is_correct, score_earned = exam.submit_answer(question, "درست")

        self.assertEqual(question.correct_answer, "True")
        self.assertTrue(is_correct)
        self.assertEqual(score_earned, 20)

    def test_submit_view_saves_multiple_answers_in_single_request(self):
        question_1 = StageQuestion.objects.create(
            question_set=self.question_set,
            text="پایتخت ایران چیست؟",
            question_number=1,
            question_type=StageQuestion.QuestionType.MULTIPLE_CHOICE,
            option1="تهران",
            option2="قم",
            option3="اصفهان",
            option4="شیراز",
            correct_answer="تهران",
            question_points=10,
        )
        question_2 = StageQuestion.objects.create(
            question_set=self.question_set,
            text="عدد را بنویسید",
            question_number=2,
            question_type=StageQuestion.QuestionType.SHORT_ANSWER,
            correct_answer="۱۲۳",
            question_points=10,
        )
        exam = self.stage_progress.start_exam(self.question_set)
        self.client.force_login(self.user)

        response = self.client.post(
            f"/learning/exams/{exam.pk}/submit/",
            {
                f"question_{question_1.pk}": "تهران",
                f"question_{question_2.pk}": "123",
            },
        )

        self.assertRedirects(response, f"/learning/exams/{exam.pk}/")
        self.assertEqual(exam.answers.count(), 2)
        self.assertTrue(exam.answers.get(question=question_1).is_correct)
        self.assertTrue(exam.answers.get(question=question_2).is_correct)

    def test_expired_exam_is_finalized_on_access(self):
        question = StageQuestion.objects.create(
            question_set=self.question_set,
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
        exam = self.stage_progress.start_exam(self.question_set)
        exam.submit_answer(question, "قم")
        expired_started_at = timezone.now() - UserStageExam.EXAM_DURATION - timedelta(minutes=1)
        UserStageExam.objects.filter(pk=exam.pk).update(started_at=expired_started_at)
        self.client.force_login(self.user)

        response = self.client.get(f"/learning/exams/{exam.pk}/")

        self.assertRedirects(
            response,
            f"/learning/progress/{self.stage_progress.user_learning_progress.pk}/",
        )
        exam.refresh_from_db()
        self.stage_progress.refresh_from_db()
        self.assertEqual(exam.status, UserStageExam.ExamStatus.FAILED)
        self.assertIsNotNone(exam.completed_at)
        self.assertEqual(self.stage_progress.status, UserStageProgress.StageStatus.FAILED_PREVIOUSLY)
