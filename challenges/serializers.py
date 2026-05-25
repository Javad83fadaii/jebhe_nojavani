from rest_framework import serializers
from .models import Challenge, ChallengeParticipation
from django.utils import timezone

class ChallengeSerializer(serializers.ModelSerializer):
    is_active_now = serializers.ReadOnlyField(source='is_currently_active')
    
    class Meta:
        model = Challenge
        fields = [
            'id', 'title', 'description', 'image', 
            'start_date', 'end_date', 'coin_reward', 'points_reward',
            'submission_type',
            'is_active', 'is_active_now', 'created_at'
        ]

class ChallengeParticipationSerializer(serializers.ModelSerializer):
    challenge_details = ChallengeSerializer(source='challenge', read_only=True)
    
    class Meta:
        model = ChallengeParticipation
        fields = [
            'id', 'challenge', 'challenge_details', 'participated_at', 
            'status', 'submitted_at', 'reviewed_at',
            'submission_text', 'attended', 'evidence',
            'is_completed', 'completed_at',
            'coins_received', 'points_received', 'reward_awarded',
        ]
        read_only_fields = [
            'participated_at',
            'status',
            'submitted_at',
            'reviewed_at',
            'is_completed',
            'completed_at',
            'coins_received',
            'points_received',
            'reward_awarded',
        ]

    def validate(self, data):
        user = self.context['request'].user
        challenge = data.get('challenge')
        
        if ChallengeParticipation.objects.filter(user=user, challenge=challenge).exists():
            raise serializers.ValidationError("شما قبلاً در این چالش شرکت کرده‌اید.")
            
        if not challenge.is_currently_active:
            raise serializers.ValidationError("این چالش در حال حاضر فعال نیست.")
            
        return data
