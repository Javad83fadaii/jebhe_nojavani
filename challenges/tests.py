from unittest.mock import Mock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from challenges.admin import ChallengeParticipationAdmin
from challenges.models import Challenge, ChallengeParticipation


class ChallengeParticipationAdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.user_model = get_user_model()

        self.creator = self.user_model.objects.create_user(
            phone_number="09120000001",
            password="testpass123",
            first_name="Admin",
            last_name="Creator",
        )
        self.participant_user = self.user_model.objects.create_user(
            phone_number="09120000002",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        self.challenge = Challenge.objects.create(
            title="چالش تست",
            description="توضیحات تست",
            start_date=timezone.now() - timezone.timedelta(days=2),
            end_date=timezone.now() - timezone.timedelta(hours=1),
            coin_reward=25,
            submission_type=Challenge.SubmissionType.ATTENDANCE,
            creator=self.creator,
        )
        self.participation = ChallengeParticipation.objects.create(
            user=self.participant_user,
            challenge=self.challenge,
            status=ChallengeParticipation.Status.SUBMITTED,
            submitted_at=timezone.now() - timezone.timedelta(days=1),
            attended=True,
        )

    @patch("challenges.admin.messages.error")
    @patch("challenges.admin.messages.success")
    def test_admin_status_change_to_approved_awards_coins(self, success_mock, error_mock):
        request = self.factory.post("/admin/challenges/challengeparticipation/")
        request.user = self.creator

        obj = ChallengeParticipation.objects.get(pk=self.participation.pk)
        obj.status = ChallengeParticipation.Status.APPROVED

        model_admin = ChallengeParticipationAdmin(ChallengeParticipation, self.site)
        model_admin.save_model(request, obj, form=Mock(), change=True)

        self.participation.refresh_from_db()
        self.participant_user.refresh_from_db()

        self.assertEqual(self.participation.status, ChallengeParticipation.Status.APPROVED)
        self.assertTrue(self.participation.reward_awarded)
        self.assertEqual(self.participation.coins_received, 25)
        self.assertEqual(self.participant_user.challenge_coins, 25)
        self.assertEqual(self.participant_user.coin_transactions.count(), 1)
        success_mock.assert_called_once()
        error_mock.assert_not_called()
