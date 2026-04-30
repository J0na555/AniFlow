from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("anime", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StreamingSource",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=128, unique=True)),
                ("base_url", models.URLField()),
                ("search_url_template", models.CharField(max_length=255)),
                ("episode_pattern", models.CharField(max_length=255)),
                ("priority", models.PositiveSmallIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="AnimeStreamingMapping",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("source_identifier", models.CharField(max_length=255)),
                ("confidence_score", models.DecimalField(decimal_places=3, max_digits=4)),
                ("verified", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "anime",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="streaming_mappings",
                        to="anime.anime",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="anime_mappings",
                        to="streaming.streamingsource",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("anime", "source"),
                        name="unique_anime_source_mapping",
                    )
                ],
            },
        ),
    ]
