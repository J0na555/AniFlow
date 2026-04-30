from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    tracker_type = models.CharField(max_length=32, blank=True)
    tracker_user_id = models.CharField(max_length=64, blank=True)
    tracker_access_token = models.TextField(blank=True)
    tracker_refresh_token = models.TextField(blank=True)
