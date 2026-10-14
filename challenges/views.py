from rest_framework import viewsets, mixins, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from pathlib import Path
from .models import Challenge, ChallengeParticipation
from .serializers import ChallengeSerializer, ChallengeParticipationSerializer
from django.core.exceptions import ValidationError
from config.upload_security import private_challenge_evidence_storage

class ChallengeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Challenge.objects.all()
    serializer_class = ChallengeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # نمایش چالش‌های فعال در لیست عمومی
        now = timezone.now()
        return Challenge.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        )

class ParticipationViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ChallengeParticipationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChallengeParticipation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        participation = self.get_object()
        evidence = request.FILES.get("evidence")
        text = request.data.get("text")
        attended = str(request.data.get("attended") or "").lower() in {"1", "true", "yes", "on"}

        try:
            participation.submit(attended=attended, text=text, evidence=evidence)
            return Response(
                {
                    "status": "success",
                    "message": "ارسال شما ثبت شد و پس از پایان چالش توسط ادمین بررسی می‌شود.",
                }
            )
        except ValidationError as e:
            return Response(
                {
                    "status": "error",
                    "message": "; ".join(e.messages),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


@login_required
def challenge_evidence_download(request):
    file_name = (request.GET.get("name") or "").strip()
    if not file_name:
        raise Http404("File not found.")

    participation = (
        ChallengeParticipation.objects.select_related("challenge", "user", "challenge__creator")
        .filter(evidence=file_name)
        .first()
    )
    if participation is None:
        raise Http404("File not found.")

    user = request.user
    can_access = (
        user.is_staff
        or participation.user_id == user.id
        or participation.challenge.creator_id == user.id
    )
    if not can_access:
        raise Http404("File not found.")

    if private_challenge_evidence_storage.exists(file_name):
        file_handle = private_challenge_evidence_storage.open(file_name, "rb")
    else:
        legacy_file_path = Path(settings.MEDIA_ROOT) / file_name
        if not legacy_file_path.exists() or not legacy_file_path.is_file():
            raise Http404("File not found.")
        file_handle = legacy_file_path.open("rb")

    response = FileResponse(
        file_handle,
        as_attachment=True,
        filename=Path(file_name).name,
        content_type="application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
