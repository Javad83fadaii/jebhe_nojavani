from django.test import TestCase

from accounts.models import Rank, User
from learning.models import LearningPath


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
