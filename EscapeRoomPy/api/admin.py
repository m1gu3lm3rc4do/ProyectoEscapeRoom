from django.contrib import admin
from .models import GameSession


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'difficulty', 'time_taken', 'correct_answers', 'questions_answered', 'completed', 'created_at')
    list_filter = ('difficulty', 'completed')
    search_fields = ('user__username',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
