from django.db import models
from django.contrib.auth.models import User

class GameSession(models.Model):
    DIFFICULTY_CHOICES = [('easy', 'Fácil'), ('medium', 'Medio'), ('hard', 'Difícil')]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    time_taken = models.FloatField(help_text="Tiempo en segundos")
    questions_answered = models.IntegerField()
    correct_answers = models.IntegerField()
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save_score(self):
        self.save()


class Room(models.Model):
    DIFFICULTY_CHOICES = [('easy', 'Fácil'), ('medium', 'Medio'), ('hard', 'Difícil')]
    STATUS_CHOICES     = [('draft', 'Borrador'), ('published', 'Publicado')]

    title        = models.CharField(max_length=100)
    description  = models.TextField(max_length=500, blank=True)
    difficulty   = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    min_correct  = models.PositiveIntegerField(default=1)
    creator      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rooms')
    created_at   = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-published_at', '-created_at']


class Question(models.Model):
    room          = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='questions')
    creator       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questions')
    text          = models.CharField(max_length=500)
    option_0      = models.CharField(max_length=200)
    option_1      = models.CharField(max_length=200)
    option_2      = models.CharField(max_length=200)
    option_3      = models.CharField(max_length=200)
    correct_index = models.PositiveSmallIntegerField()  # 0–3
    created_at    = models.DateTimeField(auto_now_add=True)


class RoomSession(models.Model):
    room               = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='sessions')
    user               = models.ForeignKey(User, on_delete=models.CASCADE, related_name='room_sessions')
    time_taken         = models.FloatField(help_text="Tiempo en segundos")
    questions_answered = models.IntegerField()
    correct_answers    = models.IntegerField()
    completed          = models.BooleanField(default=False)
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
