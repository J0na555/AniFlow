from django.db import models


class StreamingSource(models.Model):
    name = models.CharField(max_length=128, unique=True)
    base_url = models.URLField()
    search_url_template = models.CharField(max_length=255)
    episode_pattern = models.CharField(max_length=255)
    priority = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class AnimeStreamingMapping(models.Model):
    anime = models.ForeignKey(
        "anime.Anime",
        on_delete=models.CASCADE,
        related_name="streaming_mappings",
    )
    source = models.ForeignKey(
        StreamingSource,
        on_delete=models.CASCADE,
        related_name="anime_mappings",
    )
    source_identifier = models.CharField(max_length=255)
    confidence_score = models.DecimalField(max_digits=4, decimal_places=3)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["anime", "source"],
                name="unique_anime_source_mapping",
            )
        ]

    def __str__(self) -> str:
        return f"{self.anime} on {self.source}"

