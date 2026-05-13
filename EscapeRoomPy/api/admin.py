from django.contrib import admin
from .models import GameSession, Room, Question, RoomSession


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'difficulty', 'time_taken', 'correct_answers', 'questions_answered', 'completed', 'created_at')
    list_filter = ('difficulty', 'completed')
    search_fields = ('user__username',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'difficulty', 'status', 'min_correct', 'created_at', 'published_at')
    list_filter = ('difficulty', 'status')
    search_fields = ('title', 'creator__username')
    readonly_fields = ('created_at', 'published_at')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'room', 'creator', 'correct_index', 'created_at')
    list_filter = ('room', 'creator')
    search_fields = ('text', 'creator__username')
    readonly_fields = ('created_at',)


@admin.register(RoomSession)
class RoomSessionAdmin(admin.ModelAdmin):
    list_display = ('room', 'user', 'time_taken', 'correct_answers', 'questions_answered', 'completed', 'created_at')
    list_filter = ('completed', 'room')
    search_fields = ('user__username', 'room__title')
    readonly_fields = ('created_at',)
