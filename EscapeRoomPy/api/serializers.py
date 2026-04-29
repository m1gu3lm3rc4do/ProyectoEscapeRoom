from rest_framework import serializers
from django.contrib.auth.models import User
from .models import GameSession

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class SessionSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    class Meta:
        model = GameSession
        fields = '__all__'

class LeaderboardSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    class Meta:
        model = GameSession
        fields = ['username', 'time_taken', 'difficulty', 'correct_answers']