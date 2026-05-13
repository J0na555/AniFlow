from django.conf import settings
from django.db import models


class Anime(models.Model):
    tracker_type = models.CharField(max_length=32)
    tracker_id = models.CharField(max_length=64)
    title_romaji = models.CharField(max_length=255, blank=True)
    title_english = models.CharField(max_length=255, blank=True)
    title_native = models.CharField(max_length=255, blank=True)
    season = models.CharField(max_length=16, blank=True)
    season_year = models.PositiveSmallIntegerField(null=True, blank=True)
    episodes = models.PositiveSmallIntegerField(null=True, blank=True)
    studio = models.CharField(max_length=255, blank=True)
    cover_image_url = models.URLField(blank=True)
    banner_image_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tracker_type", "tracker_id"],
                name="unique_tracker_anime",
            )
        ]

    def __str__(self) -> str:
        title = self.title_english or self.title_romaji or self.title_native
        return title or f"{self.tracker_type}:{self.tracker_id}"


class UserAnime(models.Model):
    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("watching", "Watching"),
        ("planning", "Planning"),
        ("completed", "Completed"),
        ("dropped", "Dropped"),
        ("paused", "Paused"),
        ("repeating", "Repeating"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="anime_entries",
    )
    anime = models.ForeignKey(
        Anime,
        on_delete=models.CASCADE,
        related_name="user_entries",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="planning")
    progress = models.PositiveSmallIntegerField(default=0)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "anime"], name="unique_user_anime")
        ]

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.anime}"

