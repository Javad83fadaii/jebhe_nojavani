from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.models import Rank, Seller, User
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


class LogoutViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone_number="09120001111",
            password="StrongPass123!",
            first_name="خروج",
            last_name="تست",
        )
        self.client.force_login(self.user)

    def test_logout_requires_post(self):
        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_post_logs_user_out(self):
        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, "/?logout=true")
        self.assertNotIn("_auth_user_id", self.client.session)


class HomeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone_number="09120000001",
            password="StrongPass123!",
            first_name="مینا",
            last_name="کریمی",
            total_points=300,
        )
        self.public_top_user = User.objects.create_user(
            phone_number="09120000002",
            password="StrongPass123!",
            first_name="رقیه",
            last_name="صادقی",
            total_points=500,
        )
        self.staff_user = User.objects.create_user(
            phone_number="09120000003",
            password="StrongPass123!",
            first_name="ادمین",
            last_name="نمونه",
            total_points=900,
            is_staff=True,
        )
        self.seller_user = User.objects.create_user(
            phone_number="09120000004",
            password="StrongPass123!",
            first_name="فروشنده",
            last_name="نمونه",
            total_points=1000,
        )
        Seller.objects.create(
            user=self.seller_user,
            shop_name="فروشگاه نمونه",
            shop_address="آدرس فروشگاه",
        )

    def test_home_leaderboard_excludes_staff_and_sellers(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [user.id for user in response.context["leaderboard"]],
            [self.public_top_user.id, self.user.id],
        )
        self.assertEqual(response.context["user_rank"], 2)

    def test_home_leaderboard_uses_abbreviated_public_name(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "رقیه ص.")
        self.assertNotContains(response, "رقیه صادقی")

    def test_home_without_trailing_slash_redirects_to_canonical_url(self):
        self.client.force_login(self.user)

        response = self.client.get("/home")

        self.assertRedirects(response, reverse("home"), status_code=301, target_status_code=200)


class BaseTitleBlockTests(TestCase):
    def setUp(self):
        Rank.ensure_default_ranks()
        self.client = Client()
        self.user = User.objects.create_user(
            phone_number="09120000005",
            password="StrongPass123!",
            first_name="کاربر",
            last_name="تست",
        )

    def test_learning_template_title_block_overrides_base_title(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("learning:rank_cards"))

        self.assertContains(response, "<title>درجه‌بندی | جبهه نوجوانی</title>", html=True)


class AdminSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()

    @override_settings(ADMIN_URL="secret-admin/")
    def test_admin_route_uses_configured_path(self):
        self.assertEqual(reverse("admin:index"), "/secret-admin/")

    @override_settings(DEBUG=False, ADMIN_URL="secret-admin/", ADMIN_IP_ALLOWLIST=("10.10.10.10",))
    def test_admin_route_blocks_requests_outside_allowlist(self):
        response = self.client.get(reverse("admin:index"), REMOTE_ADDR="127.0.0.1")

        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=False, ADMIN_URL="secret-admin/", ADMIN_IP_ALLOWLIST=("127.0.0.1",))
    def test_admin_route_allows_allowlisted_requests(self):
        response = self.client.get(reverse("admin:index"), REMOTE_ADDR="127.0.0.1")

        self.assertEqual(response.status_code, 302)
