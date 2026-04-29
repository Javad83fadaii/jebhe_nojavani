from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

class Challenge(models.Model):
    title = models.CharField(max_length=255, verbose_name="عنوان چالش")
    description = models.TextField(verbose_name="توضیحات")
    image = models.ImageField(upload_to='challenges/', null=True, blank=True, verbose_name="تصویر چالش")
    start_date = models.DateTimeField(verbose_name="تاریخ شروع")
    end_date = models.DateTimeField(verbose_name="تاریخ پایان")
    coin_reward = models.PositiveIntegerField(verbose_name="مقدار سکه")
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='challenge_participations', verbose_name="کاربر")
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='participations', verbose_name="چالش")
    participated_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ شرکت")
    is_completed = models.BooleanField(default=False, verbose_name="وضعیت تکمیل")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تکمیل")
    coins_received = models.PositiveIntegerField(default=0, verbose_name="سکه دریافتی")
    evidence = models.FileField(upload_to='challenge_evidence/', null=True, blank=True, verbose_name="مدرک تکمیل")

    class Meta:
        verbose_name = "شرکت در چالش"
        verbose_name_plural = "شرکت در چالش‌ها"
        unique_together = ('user', 'challenge')

    def __str__(self):
        return f"{self.user.username} - {self.challenge.title}"

    def complete_challenge(self):
        if self.is_completed:
            raise ValidationError("این چالش قبلاً تکمیل شده است.")
        
        if not self.challenge.is_currently_active:
            raise ValidationError("زمان این چالش به پایان رسیده یا هنوز شروع نشده است.")

        with transaction.atomic():
            self.is_completed = True
            self.completed_at = timezone.now()
            self.coins_received = self.challenge.coin_reward
            self.save()
            
            # اضافه کردن سکه به حساب کاربر
            user = self.user
            if hasattr(user, 'challenge_coins'):
                user.challenge_coins += self.coins_received
                user.save()
            elif hasattr(user, 'profile') and hasattr(user.profile, 'challenge_coins'):
                user.profile.challenge_coins += self.coins_received
                user.profile.save()
            # اگر هیچکدام نبود، می‌توان در آینده فیلد را اضافه کرد
