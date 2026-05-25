from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Challenge, ChallengeParticipation
from .serializers import ChallengeSerializer, ChallengeParticipationSerializer
from django.core.exceptions import ValidationError

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

class ParticipationViewSet(viewsets.ModelViewSet):
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
                    "message": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=['get'], url_path='my-challenges')
    def my_challenges(self, request):
        participations = self.get_queryset()
        serializer = self.get_serializer(participations, many=True)
        return Response(serializer.data)
