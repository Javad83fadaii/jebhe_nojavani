from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

class Challenge(models.Model):
    class SubmissionType(models.TextChoices):
        ATTENDANCE = "attendance", "ثبت حضور"
        TEXT = "text", "نوشتن متن"
        IMAGE = "image", "آپلود عکس"
        VIDEO = "video", "آپلود فیلم"

    title = models.CharField(max_length=255, verbose_name="عنوان چالش")
    description = models.TextField(verbose_name="توضیحات")
    image = models.ImageField(upload_to='challenges/', null=True, blank=True, verbose_name="تصویر چالش")
    start_date = models.DateTimeField(verbose_name="تاریخ شروع")
    end_date = models.DateTimeField(verbose_name="تاریخ پایان")
    coin_reward = models.PositiveIntegerField(verbose_name="مقدار سکه")
    submission_type = models.CharField(
        max_length=20,
        choices=SubmissionType.choices,
        default=SubmissionType.ATTENDANCE,
        verbose_name="نوع چالش",
    )
    is_active = models.BooleanField(default=True, verbose_name="وضعیت فعال/غیرفعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_challenges', verbose_name="ایجادکننده")

    def __str__(self):
        return self.title

    @property
    def is_currently_active(self):
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date

    class Meta:
        verbose_name = "چالش"
        verbose_name_plural = "چالش‌ها"
        ordering = ['-created_at']

class ChallengeParticipation(models.Model):
    class Status(models.TextChoices):
        JOINED = "joined", "ثبت‌نام"
        SUBMITTED = "submitted", "ارسال شده"
        APPROVED = "approved", "تایید شده"
        REJECTED = "rejected", "رد شده"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='challenge_participations', verbose_name="کاربر")
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='participations', verbose_name="چالش")
    participated_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ شرکت")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.JOINED, verbose_name="وضعیت")
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ ارسال")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ بررسی ادمین")
    submission_text = models.TextField(blank=True, default="", verbose_name="متن ارسال شده")
    attended = models.BooleanField(default=False, verbose_name="ثبت حضور توسط کاربر")
    is_completed = models.BooleanField(default=False, verbose_name="تایید و ثبت نهایی")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تکمیل")
    coins_received = models.PositiveIntegerField(default=0, verbose_name="سکه دریافتی")
    reward_awarded = models.BooleanField(default=False, verbose_name="پاداش پرداخت شده")
    evidence = models.FileField(upload_to='challenge_evidence/', null=True, blank=True, verbose_name="فایل ارسالی")

    class Meta:
        verbose_name = "شرکت در چالش"
        verbose_name_plural = "شرکت در چالش‌ها"
        unique_together = ('user', 'challenge')

    def __str__(self):
        return f"{self.user} - {self.challenge.title}"

    def submit(self, *, attended: bool = False, text: str | None = None, evidence=None):
        if self.status in {self.Status.APPROVED, self.Status.REJECTED}:
            raise ValidationError("این ارسال قبلاً بررسی شده است.")

        if not self.challenge.is_currently_active:
            raise ValidationError("زمان این چالش به پایان رسیده یا هنوز شروع نشده است.")

        submission_type = self.challenge.submission_type
        if submission_type == Challenge.SubmissionType.ATTENDANCE:
            if not attended:
                raise ValidationError("برای ثبت حضور باید گزینه «شرکت می‌کنم» را تایید کنید.")
            self.attended = True
        elif submission_type == Challenge.SubmissionType.TEXT:
            normalized_text = (text or "").strip()
            if not normalized_text:
                raise ValidationError("متن ارسال شده نمی‌تواند خالی باشد.")
            self.submission_text = normalized_text
        elif submission_type in {Challenge.SubmissionType.IMAGE, Challenge.SubmissionType.VIDEO}:
            if not evidence:
                raise ValidationError("فایل ارسالی الزامی است.")
            content_type = getattr(evidence, "content_type", "") or ""
            if submission_type == Challenge.SubmissionType.IMAGE and content_type and not content_type.startswith("image/"):
                raise ValidationError("برای این چالش باید فایل عکس ارسال کنید.")
            if submission_type == Challenge.SubmissionType.VIDEO and content_type and not content_type.startswith("video/"):
                raise ValidationError("برای این چالش باید فایل ویدئو ارسال کنید.")
            self.evidence = evidence
        else:
            raise ValidationError("نوع چالش نامعتبر است.")

        self.status = self.Status.SUBMITTED
        self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_at", "submission_text", "attended", "evidence"])

    def approve_and_award(self):
        if self.reward_awarded:
            return

        if timezone.now() < self.challenge.end_date:
            raise ValidationError("این چالش هنوز به پایان نرسیده است.")

        if self.status != self.Status.SUBMITTED:
            raise ValidationError("ابتدا باید ارسال کاربر ثبت شده باشد تا بتوان آن را تایید کرد.")

        coins = int(self.challenge.coin_reward or 0)
        now = timezone.now()

        with transaction.atomic():
            if coins > 0:
                self.user.add_coins(coins, f"پاداش چالش: {self.challenge.title}", challenge=self.challenge)

            self.status = self.Status.APPROVED
            self.reviewed_at = now
            self.is_completed = True
            self.completed_at = now
            self.reward_awarded = True
            self.coins_received = coins
            self.save(
                update_fields=[
                    "status",
                    "reviewed_at",
                    "is_completed",
                    "completed_at",
                    "reward_awarded",
                    "coins_received",
                ]
            )

    def reject(self):
        if self.reward_awarded:
            raise ValidationError("برای ارسال تایید شده امکان رد کردن وجود ندارد.")

        if self.status != self.Status.SUBMITTED:
            raise ValidationError("فقط ارسال‌های ثبت شده قابل رد کردن هستند.")

        self.status = self.Status.REJECTED
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_at"])
