from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Anime",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("tracker_type", models.CharField(max_length=32)),
                ("tracker_id", models.CharField(max_length=64)),
                ("title_romaji", models.CharField(blank=True, max_length=255)),
                ("title_english", models.CharField(blank=True, max_length=255)),
                ("title_native", models.CharField(blank=True, max_length=255)),
                ("season", models.CharField(blank=True, max_length=16)),
                ("season_year", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("episodes", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("studio", models.CharField(blank=True, max_length=255)),
                ("cover_image_url", models.URLField(blank=True)),
                ("banner_image_url", models.URLField(blank=True)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tracker_type", "tracker_id"),
                        name="unique_tracker_anime",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="UserAnime",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("watching", "Watching"),
                            ("planning", "Planning"),
                            ("completed", "Completed"),
                            ("dropped", "Dropped"),
                            ("paused", "Paused"),
                            ("repeating", "Repeating"),
                        ],
                        default="planning",
                        max_length=16,
                    ),
                ),
                ("progress", models.PositiveSmallIntegerField(default=0)),
                (
                    "score",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
                ),
                ("start_date", models.DateField(blank=True, null=True)),
                ("completed_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "anime",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="user_entries",
                        to="anime.anime",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="anime_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("user", "anime"), name="unique_user_anime")
                ],
            },
        ),
    ]
