from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_migrate, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.models import CoinToWalletTransfer, CoinTransaction, Rank, Seller, User


@receiver(post_migrate)
def ensure_default_ranks(sender, **kwargs):
    if sender.label != "accounts":
        return
    Rank.ensure_default_ranks()


@receiver(pre_save, sender=User)
def sync_user_rank(sender, instance: User, **kwargs):
    instance.current_rank = Rank.get_rank_for_points(instance.total_points)


@receiver(pre_save, sender=Seller)
def sync_seller_verification(sender, instance: Seller, **kwargs):
    previous_verified = None
    if instance.pk:
        previous_verified = Seller.objects.filter(pk=instance.pk).values_list("verified", flat=True).first()

    if instance.verified and not instance.verified_at:
        instance.verified_at = timezone.now()
    elif previous_verified is True and not instance.verified:
        instance.verified_at = None


@receiver(pre_save, sender=CoinToWalletTransfer)
def prepare_transfer_processing(sender, instance: CoinToWalletTransfer, **kwargs):
    instance._previous_status = None
    if instance.pk:
        instance._previous_status = (
            CoinToWalletTransfer.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
        )

    status_changed = instance._previous_status != instance.status
    if status_changed and instance.status in {
        CoinToWalletTransfer.TransferStatus.APPROVED,
        CoinToWalletTransfer.TransferStatus.REJECTED,
    }:
        instance.processed_at = timezone.now()

    if (
        instance.status == CoinToWalletTransfer.TransferStatus.APPROVED
        and instance._previous_status != CoinToWalletTransfer.TransferStatus.APPROVED
        and instance.user.challenge_coins < instance.coin_amount
    ):
        raise ValidationError("موجودی سکه کاربر برای تایید این انتقال کافی نیست.")


@receiver(post_save, sender=CoinToWalletTransfer)
def process_approved_transfer(sender, instance: CoinToWalletTransfer, created: bool, **kwargs):
    if instance.status != CoinToWalletTransfer.TransferStatus.APPROVED:
        return
    if getattr(instance, "_previous_status", None) == CoinToWalletTransfer.TransferStatus.APPROVED:
        return

    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=instance.user_id)
        if user.challenge_coins < instance.coin_amount:
            raise ValidationError("موجودی سکه کاربر برای انتقال کافی نیست.")

        User.objects.filter(pk=user.pk).update(
            challenge_coins=F("challenge_coins") - instance.coin_amount,
            wallet_balance=F("wallet_balance") + Decimal(instance.amount_toman),
        )

        CoinTransaction.objects.create(
            user=user,
            amount=-instance.coin_amount,
            transaction_type=CoinTransaction.TransactionType.WALLET_TRANSFER,
            description=f"انتقال {instance.coin_amount} سکه به کیف پول. شناسه درخواست: {instance.pk}",
            transaction_date=instance.processed_at or timezone.now(),
        )
