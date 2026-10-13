import io
import tempfile
from unittest.mock import Mock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

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

    def test_approve_and_award_is_idempotent_for_stale_instances(self):
        stale_first = ChallengeParticipation.objects.get(pk=self.participation.pk)
        stale_second = ChallengeParticipation.objects.get(pk=self.participation.pk)

        stale_first.approve_and_award()
        stale_second.approve_and_award()

        self.participation.refresh_from_db()
        self.participant_user.refresh_from_db()

        self.assertEqual(self.participation.status, ChallengeParticipation.Status.APPROVED)
        self.assertTrue(self.participation.reward_awarded)
        self.assertEqual(self.participation.coins_received, 25)
        self.assertEqual(self.participant_user.challenge_coins, 25)
        self.assertEqual(self.participant_user.coin_transactions.count(), 1)


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    PRIVATE_MEDIA_ROOT=tempfile.mkdtemp(),
)
class ChallengeEvidenceSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_model = get_user_model()
        self.creator = self.user_model.objects.create_user(
            phone_number="09120000111",
            password="testpass123",
            first_name="Creator",
            last_name="Admin",
        )
        self.participant_user = self.user_model.objects.create_user(
            phone_number="09120000112",
            password="testpass123",
            first_name="Participant",
            last_name="User",
        )
        self.other_user = self.user_model.objects.create_user(
            phone_number="09120000113",
            password="testpass123",
            first_name="Other",
            last_name="User",
        )
        self.challenge = Challenge.objects.create(
            title="چالش مدرک",
            description="توضیحات",
            start_date=timezone.now() - timezone.timedelta(hours=1),
            end_date=timezone.now() + timezone.timedelta(days=1),
            coin_reward=10,
            submission_type=Challenge.SubmissionType.IMAGE,
            creator=self.creator,
        )
        self.participation = ChallengeParticipation.objects.create(
            user=self.participant_user,
            challenge=self.challenge,
        )
        self.client.force_login(self.participant_user)

    def _build_valid_png(self, file_name: str = "evidence.png") -> SimpleUploadedFile:
        image_buffer = io.BytesIO()
        image = Image.new("RGB", (20, 20), color=(50, 100, 150))
        image.save(image_buffer, format="PNG")
        return SimpleUploadedFile(file_name, image_buffer.getvalue(), content_type="image/png")

    def test_submit_rejects_spoofed_html_file_even_with_image_content_type(self):
        response = self.client.post(
            f"/challenges-system/api/participations/{self.participation.pk}/complete/",
            {
                "evidence": SimpleUploadedFile(
                    "fake.jpg",
                    b"<html><body>xss</body></html>",
                    content_type="image/jpeg",
                )
            },
        )

        self.assertEqual(response.status_code, 400)
        self.participation.refresh_from_db()
        self.assertFalse(bool(self.participation.evidence))
        self.assertIn("نوع واقعی فایل معتبر نیست", response.json()["message"])

    def test_submit_stores_evidence_behind_protected_download_url(self):
        response = self.client.post(
            f"/challenges-system/api/participations/{self.participation.pk}/complete/",
            {"evidence": self._build_valid_png()},
        )

        self.assertEqual(response.status_code, 200)
        self.participation.refresh_from_db()
        self.assertTrue(self.participation.evidence.name.startswith("challenge_evidence/"))
        self.assertIn(reverse("challenge-evidence-download"), self.participation.evidence.url)
        self.assertNotIn("/media/", self.participation.evidence.url)

    def test_protected_download_requires_related_user_permission(self):
        self.participation.submit(evidence=self._build_valid_png())
        download_url = f"{reverse('challenge-evidence-download')}?name={self.participation.evidence.name}"

        participant_response = self.client.get(download_url)
        self.assertEqual(participant_response.status_code, 200)
        self.assertEqual(participant_response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(participant_response["Cache-Control"], "private, no-store")

        self.client.force_login(self.other_user)
        other_response = self.client.get(download_url)
        self.assertEqual(other_response.status_code, 404)
