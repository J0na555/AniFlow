from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    tracker_type = models.CharField(max_length=32, blank=True)
    tracker_user_id = models.CharField(max_length=64, blank=True)
    tracker_access_token = models.TextField(blank=True)
    tracker_refresh_token = models.TextField(blank=True)


class UserSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="settings",
    )
    preferred_source = models.ForeignKey(
        "streaming.StreamingSource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preferred_by_users",
    )
    max_watching_limit = models.PositiveSmallIntegerField(default=0)
    ignore_watching_limit = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Settings for {self.user.username}"
