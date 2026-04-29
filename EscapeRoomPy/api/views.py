from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q
from .models import GameSession
from .serializers import UserSerializer, SessionSerializer, LeaderboardSerializer


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
