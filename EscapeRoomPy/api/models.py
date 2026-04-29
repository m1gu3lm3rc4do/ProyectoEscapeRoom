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
# Create your models here.
