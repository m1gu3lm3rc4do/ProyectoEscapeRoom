from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q
from django.utils import timezone
from .models import GameSession, Room, Question, RoomSession
from .serializers import (
    UserSerializer, SessionSerializer, LeaderboardSerializer,
    QuestionSerializer, RoomSerializer, RoomPublicSerializer,
    RoomSessionSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]


class GameSessionViewSet(viewsets.ModelViewSet):
    queryset = GameSession.objects.all()
    serializer_class = SessionSerializer


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def leaderboard(request):
    top = GameSession.objects.filter(completed=True).order_by('time_taken')[:10]
    return Response(LeaderboardSerializer(top, many=True).data)


@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def admin_stats(request):
    stats = GameSession.objects.aggregate(
        total_games=Count('id'),
        avg_time=Avg('time_taken'),
        easy=Count('id', filter=Q(difficulty='easy')),
        medium=Count('id', filter=Q(difficulty='medium')),
        hard=Count('id', filter=Q(difficulty='hard'))
    )
    return Response(stats)


# ── Task 3.1 ──────────────────────────────────────────────────────────────────

class RoomViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Room CRUD, publish action, questions listing, and stats.

    Requirements: 2.1, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 3.1, 3.2, 3.3, 5.4, 5.5
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        difficulty = self.request.query_params.get('difficulty')

        if user.is_authenticated:
            # Published rooms + all rooms owned by the requesting user
            qs = Room.objects.filter(
                Q(status='published') | Q(creator=user)
            ).distinct().order_by('-published_at', '-created_at')
        else:
            qs = Room.objects.filter(status='published').order_by('-published_at')

        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        return qs

    def get_serializer_class(self):
        user = self.request.user
        # Use full serializer only for authenticated creators on non-retrieve actions
        if user.is_authenticated and self.action != 'retrieve':
            return RoomSerializer
        return RoomPublicSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def destroy(self, request, *args, **kwargs):
        room = self.get_object()
        if room.status == 'published' and room.sessions.exists():
            return Response(
                {'detail': 'No se puede eliminar una Room publicada que ya tiene sesiones de juego.'},
                status=409
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def publish(self, request, pk=None):
        room = self.get_object()

        if request.user != room.creator:
            return Response({'detail': 'No tienes permiso para publicar esta Room.'}, status=403)

        question_count = room.questions.count()
        if not (4 <= question_count <= 62):
            return Response(
                {
                    'detail': (
                        f'La Room debe tener entre 4 y 62 preguntas para publicarse. '
                        f'Actualmente tiene {question_count}.'
                    )
                },
                status=400
            )

        room.status = 'published'
        room.published_at = timezone.now()
        room.save()

        serializer = RoomSerializer(room, context={'request': request})
        return Response(serializer.data, status=200)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def questions(self, request, pk=None):
        room = self.get_object()
        qs = room.questions.all()
        serializer = QuestionSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def stats(self, request, pk=None):
        room = self.get_object()

        if request.user != room.creator:
            return Response({'detail': 'No tienes permiso para ver las estadísticas de esta Room.'}, status=403)

        sessions = room.sessions.all()
        total_games = sessions.count()

        if total_games == 0:
            avg_time = None
            completion_rate = 0.0
        else:
            agg = sessions.aggregate(avg_time=Avg('time_taken'))
            avg_time = agg['avg_time']
            completed_count = sessions.filter(completed=True).count()
            completion_rate = (completed_count / total_games) * 100

        return Response({
            'total_games': total_games,
            'avg_time': avg_time,
            'completion_rate': completion_rate,
        })


# ── Task 3.6 ──────────────────────────────────────────────────────────────────

class QuestionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Question CRUD — scoped to the authenticated creator.

    Requirements: 1.1, 1.4, 1.5, 1.6, 1.7
    """

    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Question.objects.filter(creator=self.request.user)

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def get_object(self):
        obj = super().get_object()
        if obj.creator != self.request.user:
            raise PermissionDenied('No tienes permiso para acceder a esta pregunta.')
        return obj


# ── Task 3.9 ──────────────────────────────────────────────────────────────────

class RoomSessionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for RoomSession — scoped to the authenticated user.

    Requirements: 4.4, 5.1, 5.2
    """

    serializer_class = RoomSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RoomSession.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
