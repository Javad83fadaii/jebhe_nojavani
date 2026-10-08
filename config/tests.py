from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from accounts.models import Rank, User
from config.context_processors import user_points


class UserProgressSyncTests(TestCase):
    def setUp(self):
        Rank.ensure_default_ranks()
        self.factory = RequestFactory()
        self.client = Client()
        self.user = User.objects.create_user(
            phone_number="09123335555",
            password="StrongPass123!",
            first_name="پیشرفت",
            last_name="آزمایشی",
            total_points=1500,
        )

    def test_user_points_context_uses_real_rank_range(self):
        request = self.factory.get("/")
        request.user = self.user

        context = user_points(request)

        self.assertEqual(context["user_total_points"], 1500)
        self.assertEqual(context["user_current_rank"], "افسر 5")
        self.assertEqual(context["user_points_per_level"], 1000)
        self.assertEqual(context["user_level_points"], 500)
        self.assertEqual(context["user_level_number"], 2)
        self.assertEqual(context["user_level_progress_percent"], 50)

    def test_user_progress_api_uses_real_rank_range(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("user-progress-api"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "total_points": 1500,
                "points_per_level": 1000,
                "level_points": 500,
                "level_number": 2,
                "level_progress_percent": 50,
                "current_rank": "افسر 5",
            },
        )

    def test_progress_metrics_fill_rank_at_999_points(self):
        self.user.total_points = 999
        self.user.save(update_fields=["total_points", "updated_at"])

        request = self.factory.get("/")
        request.user = self.user
        context = user_points(request)

        self.assertEqual(context["user_current_rank"], "افسر 6")
        self.assertEqual(context["user_points_per_level"], 1000)
        self.assertEqual(context["user_level_points"], 999)
        self.assertEqual(context["user_level_number"], 1)
        self.assertEqual(context["user_level_progress_percent"], 100)

    def test_progress_metrics_reset_on_new_rank_at_1000_points(self):
        self.user.total_points = 1000
        self.user.save(update_fields=["total_points", "updated_at"])

        self.client.force_login(self.user)
        response = self.client.get(reverse("user-progress-api"))

        self.assertJSONEqual(
            response.content,
            {
                "total_points": 1000,
                "points_per_level": 1000,
                "level_points": 0,
                "level_number": 2,
                "level_progress_percent": 0,
                "current_rank": "افسر 5",
            },
        )
