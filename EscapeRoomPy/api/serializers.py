from rest_framework import serializers
from django.contrib.auth.models import User
from .models import GameSession, Room, Question, RoomSession


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


# ── Task 2.1 ──────────────────────────────────────────────────────────────────

class QuestionSerializer(serializers.ModelSerializer):
    """Full serializer for Question (used by Creator API)."""

    creator = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Question
        fields = '__all__'

    def validate_correct_index(self, value):
        if value not in {0, 1, 2, 3}:
            raise serializers.ValidationError(
                "correct_index debe ser 0, 1, 2 o 3."
            )
        return value

    def validate_text(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                "El texto de la pregunta no puede estar vacío."
            )
        if len(value) > 500:
            raise serializers.ValidationError(
                "El texto de la pregunta no puede superar los 500 caracteres."
            )
        return value


# ── Task 2.3 ──────────────────────────────────────────────────────────────────

class RoomSerializer(serializers.ModelSerializer):
    """Full serializer for Room (used by Creator API)."""

    questions = QuestionSerializer(many=True, read_only=True)
    creator = serializers.ReadOnlyField(source='creator.username')
    creator_name = serializers.ReadOnlyField(source='creator.username')
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = '__all__'

    def get_question_count(self, obj):
        return obj.questions.count()

    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                "El título no puede estar vacío."
            )
        if len(value) > 100:
            raise serializers.ValidationError(
                "El título no puede superar los 100 caracteres."
            )
        return value

    def validate_difficulty(self, value):
        if value not in {'easy', 'medium', 'hard'}:
            raise serializers.ValidationError(
                "La dificultad debe ser 'easy', 'medium' o 'hard'."
            )
        return value

    def validate(self, attrs):
        # Cross-field: min_correct must not exceed the number of questions.
        # Only enforced on update (instance already exists).
        if self.instance is not None:
            min_correct = attrs.get('min_correct', self.instance.min_correct)
            question_count = self.instance.questions.count()
            if min_correct > question_count:
                raise serializers.ValidationError(
                    {
                        'min_correct': (
                            f"min_correct ({min_correct}) no puede ser mayor que "
                            f"el número de preguntas ({question_count})."
                        )
                    }
                )
        return attrs


# ── Task 2.5 ──────────────────────────────────────────────────────────────────

class QuestionPublicSerializer(serializers.ModelSerializer):
    """Public serializer for Question — excludes correct_index."""

    class Meta:
        model = Question
        exclude = ['correct_index']


class RoomPublicSerializer(serializers.ModelSerializer):
    """Public serializer for Room — questions without correct_index."""

    questions = QuestionPublicSerializer(many=True, read_only=True)
    creator_name = serializers.ReadOnlyField(source='creator.username')
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = '__all__'

    def get_question_count(self, obj):
        return obj.questions.count()


# ── Task 2.7 ──────────────────────────────────────────────────────────────────

class RoomSessionSerializer(serializers.ModelSerializer):
    """Serializer for RoomSession — user is set by the view."""

    room_title = serializers.ReadOnlyField(source='room.title')
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = RoomSession
        fields = '__all__'