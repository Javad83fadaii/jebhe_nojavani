from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from learning.models import LearningPath, UserLearningProgress, UserStageProgress


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Rank(TimestampedModel):
    POINTS_PER_LEVEL = 1000
    DEFAULT_RANKS = (
        (1, "افسر 1"),
        (2, "افسر 2"),
        (3, "افسر 3"),
        (4, "افسر 4"),
        (5, "افسر 5"),
        (6, "افسر 6"),
        (7, "ارشد 1"),
        (8, "ارشد 2"),
        (9, "ارشد 3"),
        (10, "ارشد 4"),
        (11, "ارشد 5"),
        (12, "ارشد 6"),
    )

    name = models.CharField(max_length=50, unique=True)
    level = models.PositiveSmallIntegerField(unique=True, validators=[MinValueValidator(1)])
    min_points = models.PositiveIntegerField(null=True, blank=True)
    max_points = models.PositiveIntegerField(null=True, blank=True)
    icon = models.ImageField(upload_to="ranks/", null=True, blank=True)
    color = models.CharField(max_length=7, default="#000000")

    class Meta:
        ordering = ("level",)
        verbose_name = "رتبه"
        verbose_name_plural = "رتبه‌ها"

    def __str__(self) -> str:
        if self.max_points is None:
            return f"{self.name} ({self.min_points}+)"
        return f"{self.name} ({self.min_points}-{self.max_points})"

    def save(self, *args, **kwargs):
        if self.min_points is None:
            self.min_points = (self.level - 1) * self.POINTS_PER_LEVEL
        if self.max_points is None and self.level < len(self.DEFAULT_RANKS):
            self.max_points = (self.level * self.POINTS_PER_LEVEL) - 1
        if self.level >= len(self.DEFAULT_RANKS):
            self.max_points = None
        super().save(*args, **kwargs)

    @classmethod
    def get_rank_for_points(cls, points: int | None) -> Rank | None:
        normalized_points = max(points or 0, 0)
        return cls.objects.filter(min_points__lte=normalized_points).order_by("-min_points", "-level").first()

    @classmethod
    def ensure_default_ranks(cls):
        total_levels = len(cls.DEFAULT_RANKS)
        for level, name in cls.DEFAULT_RANKS:
            min_points = (level - 1) * cls.POINTS_PER_LEVEL
            max_points = None if level == total_levels else (level * cls.POINTS_PER_LEVEL) - 1
            rank, created = cls.objects.get_or_create(
                level=level,
                defaults={
                    "name": name,
                    "min_points": min_points,
                    "max_points": max_points,
                },
            )
            if created:
                continue

            changed_fields: list[str] = []
            if rank.name != name:
                rank.name = name
                changed_fields.append("name")
            if rank.min_points != min_points:
                rank.min_points = min_points
                changed_fields.append("min_points")
            if rank.max_points != max_points:
                rank.max_points = max_points
                changed_fields.append("max_points")
            if changed_fields:
                changed_fields.append("updated_at")
                rank.save(update_fields=changed_fields)


class UserManager(BaseUserManager):
    def create_user(self, phone_number: str, password: str | None = None, **extra_fields):
        if not phone_number:
            raise ValueError("phone_number is required")

        phone_number = str(phone_number).strip()
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(phone_number=phone_number, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Gender(models.TextChoices):
        MALE = "male", "male"
        FEMALE = "female", "female"
        OTHER = "other", "other"

    phone_number = models.CharField(max_length=11, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    national_code = models.CharField(max_length=10, unique=True, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(
        choices=Gender.choices,
        max_length=10,
        null=True,
        blank=True,
    )
    profile_image = models.ImageField(upload_to="profiles/", null=True, blank=True)

    total_points = models.PositiveIntegerField(default=0)
    challenge_coins = models.PositiveIntegerField(default=0)
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    current_rank = models.ForeignKey(
        Rank,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )

    school = models.ForeignKey(
        "geography.School",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="students",
    )
    mosque = models.ForeignKey(
        "geography.Mosque",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )
    city = models.CharField(max_length=50, null=True, blank=True)
    province = models.CharField(max_length=50, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        ordering = ("-date_joined",)
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self) -> str:
        full_name = self.get_full_name()
        return full_name or self.phone_number

    @property
    def is_seller(self) -> bool:
        return hasattr(self, "seller_profile")

    @property
    def seller_verified(self) -> bool:
        seller_profile = getattr(self, "seller_profile", None)
        return bool(seller_profile and seller_profile.verified)

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def calculate_rank(self) -> Rank | None:
        rank = Rank.get_rank_for_points(self.total_points)
        self.current_rank = rank
        return rank

    def add_coins(self, amount: int, description: str, challenge=None):
        if amount <= 0:
            raise ValidationError("مقدار سکه باید بیشتر از صفر باشد.")
        if not self.pk:
            raise ValidationError("کاربر باید ذخیره شده باشد.")

        challenge_reference = ""
        if challenge is not None:
            challenge_reference = str(getattr(challenge, "pk", challenge))

        with transaction.atomic():
            CoinTransaction.objects.create(
                user=self,
                amount=amount,
                transaction_type=CoinTransaction.TransactionType.CHALLENGE_EARNED,
                description=description,
                challenge=challenge_reference or None,
            )
            User.objects.filter(pk=self.pk).update(challenge_coins=F("challenge_coins") + amount)

        self.refresh_from_db(fields=["challenge_coins"])
        return self.challenge_coins

    def transfer_coins_to_wallet(self, amount: int):
        if amount <= 0:
            raise ValidationError("مقدار انتقال باید بیشتر از صفر باشد.")
        if amount > self.challenge_coins:
            raise ValidationError("موجودی سکه چالش کافی نیست.")
        if not self.pk:
            raise ValidationError("کاربر باید ذخیره شده باشد.")

        return CoinToWalletTransfer.objects.create(
            user=self,
            coin_amount=amount,
            amount_toman=amount,
        )

    def get_exam_history(self):
        return self.exam_records.select_related("rank_at_exam").all()

    def has_perm(self, perm, obj=None) -> bool:
        if self.is_superuser:
            return True
        return super().has_perm(perm, obj=obj)

    def has_module_perms(self, app_label) -> bool:
        if self.is_superuser:
            return True
        return super().has_module_perms(app_label)

    def enroll_in_path(self, learning_path: LearningPath) -> UserLearningProgress:
        """
        Registers the user in a learning path.
        If already enrolled, returns the existing progress.
        """
        user_progress, created = UserLearningProgress.objects.get_or_create(
            user=self,
            learning_path=learning_path,
            defaults={
                "status": UserLearningProgress.ProgressStatus.IN_PROGRESS,
            },
        )
        return user_progress

    def get_learning_paths(self):
        """
        Returns all learning paths the user is enrolled in.
        """
        return self.learning_progresses.select_related("learning_path").all()

    def get_active_learning_path(self) -> UserLearningProgress | None:
        """
        Returns the user's active learning path (in_progress).
        """
        return self.learning_progresses.filter(status=UserLearningProgress.ProgressStatus.IN_PROGRESS).first()


class ExamRecord(TimestampedModel):
    class ExamStatus(models.TextChoices):
        PASSED = "passed", "قبول"
        FAILED = "failed", "مردود"
        ABSENT = "absent", "غایب"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="exam_records")
    exam_name = models.CharField(max_length=255)
    score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=7, decimal_places=2)
    exam_date = models.DateField()
    rank_at_exam = models.ForeignKey(
        Rank,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exam_records",
    )
    status = models.CharField(max_length=10, choices=ExamStatus.choices, default=ExamStatus.PASSED)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-exam_date", "-created_at")
        verbose_name = "کارنامه آزمون"
        verbose_name_plural = "کارنامه‌های آزمون"

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} - {self.exam_name}"

    def clean(self):
        if self.max_score <= 0:
            raise ValidationError({"max_score": "حداکثر نمره باید بیشتر از صفر باشد."})
        if self.score < 0:
            raise ValidationError({"score": "نمره نمی‌تواند منفی باشد."})
        if self.score > self.max_score:
            raise ValidationError({"score": "نمره کسب شده نمی‌تواند بیشتر از حداکثر نمره باشد."})

    def save(self, *args, **kwargs):
        if self.rank_at_exam_id is None and self.user_id:
            self.rank_at_exam = self.user.calculate_rank()
        self.full_clean()
        super().save(*args, **kwargs)


class CoinTransaction(TimestampedModel):
    class TransactionType(models.TextChoices):
        CHALLENGE_EARNED = "challenge_earned", "کسب از چالش"
        WALLET_TRANSFER = "wallet_transfer", "انتقال به کیف پول"
        REWARD = "reward", "جایزه"
        PENALTY = "penalty", "جریمه"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="coin_transactions")
    amount = models.IntegerField()
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    description = models.TextField(blank=True)
    transaction_date = models.DateTimeField(default=timezone.now, db_index=True)
    challenge = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ("-transaction_date", "-created_at")
        verbose_name = "تراکنش سکه"
        verbose_name_plural = "تراکنش‌های سکه"

    def __str__(self) -> str:
        return f"{self.user.phone_number} | {self.amount:+} | {self.get_transaction_type_display()}"

    def clean(self):
        if self.amount == 0:
            raise ValidationError({"amount": "مقدار تراکنش نمی‌تواند صفر باشد."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class CoinToWalletTransfer(TimestampedModel):
    class TransferStatus(models.TextChoices):
        PENDING = "pending", "در انتظار"
        APPROVED = "approved", "تایید شده"
        REJECTED = "rejected", "رد شده"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="coin_wallet_transfers")
    coin_amount = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    amount_toman = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=TransferStatus.choices, default=TransferStatus.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-requested_at", "-created_at")
        verbose_name = "انتقال سکه به کیف پول"
        verbose_name_plural = "انتقال‌های سکه به کیف پول"

    def __str__(self) -> str:
        return f"{self.user.phone_number} - {self.coin_amount} سکه"

    def clean(self):
        if self.coin_amount <= 0:
            raise ValidationError({"coin_amount": "تعداد سکه باید بیشتر از صفر باشد."})

    def save(self, *args, **kwargs):
        self.amount_toman = self.coin_amount
        self.full_clean()
        super().save(*args, **kwargs)


class Seller(TimestampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="seller_profile")
    shop_name = models.CharField(max_length=150)
    shop_address = models.TextField()
    shop_phone_number = models.CharField(max_length=20, blank=True)
    shop_description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="sellers/logos/", null=True, blank=True)
    verified = models.BooleanField(default=False)
    registered_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("5.00"))],
    )
    sales_count = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    platform_commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-registered_at", "-created_at")
        verbose_name = "فروشنده"
        verbose_name_plural = "فروشندگان"

    def __str__(self) -> str:
        return self.shop_name

    def calculate_rating(self, reviews: Iterable[Any] | None = None):
        if reviews is None:
            related_reviews = getattr(self, "reviews", None)
            if related_reviews is None:
                return self.rating
            reviews = related_reviews.all() if hasattr(related_reviews, "all") else related_reviews

        normalized_ratings: list[Decimal] = []
        for review in reviews:
            value = getattr(review, "rating", review)
            try:
                normalized_ratings.append(Decimal(str(value)))
            except Exception:
                continue

        if not normalized_ratings:
            return self.rating

        average = sum(normalized_ratings) / Decimal(len(normalized_ratings))
        average = min(max(average, Decimal("0.00")), Decimal("5.00")).quantize(Decimal("0.01"))
        self.rating = average
        self.save(update_fields=["rating", "updated_at"])
        return self.rating

    def update_total_sales(self, sales_count: int | None = None, revenue=None):
        if sales_count is None or revenue is None:
            related_orders = getattr(self, "orders", None)
            if related_orders is not None and hasattr(related_orders, "aggregate"):
                aggregates = related_orders.aggregate(
                    calculated_sales_count=models.Count("id"),
                    calculated_revenue=models.Sum("total_amount"),
                )
                if sales_count is None:
                    sales_count = aggregates["calculated_sales_count"] or 0
                if revenue is None:
                    revenue = aggregates["calculated_revenue"] or 0

        self.sales_count = sales_count if sales_count is not None else self.sales_count
        self.total_revenue = revenue if revenue is not None else self.total_revenue
        self.save(update_fields=["sales_count", "total_revenue", "updated_at"])
        return {
            "sales_count": self.sales_count,
            "total_revenue": self.total_revenue,
        }
