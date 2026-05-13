from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'sessions', views.GameSessionViewSet)
router.register(r'rooms', views.RoomViewSet, basename='room')
router.register(r'questions', views.QuestionViewSet, basename='question')
router.register(r'room-sessions', views.RoomSessionViewSet, basename='roomsession')

urlpatterns = [
    path('', include(router.urls)),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('admin-stats/', views.admin_stats, name='admin-stats'),
]