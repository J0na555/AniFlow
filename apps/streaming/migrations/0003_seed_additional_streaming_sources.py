from django.db import migrations


def seed_additional_streaming_sources(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    sources = [
        {
            "name": "Gogoanime",
            "base_url": "https://anitaku.bz",
            "search_url_template": "https://anitaku.bz/search.html?keyword={query}",
            "episode_pattern": "{slug}-episode-{episode}",
            "priority": 10,
            "is_active": True,
        },
        {
            "name": "AniTaku",
            "base_url": "https://anitaku.bz",
            "search_url_template": "https://anitaku.bz/search.html?keyword={query}",
            "episode_pattern": "{slug}-episode-{episode}",
            "priority": 20,
            "is_active": True,
        },
        {
            "name": "Crunchyroll",
            "base_url": "https://www.crunchyroll.com",
            "search_url_template": "https://www.crunchyroll.com/search?q={query}",
            "episode_pattern": "",
            "priority": 100,
            "is_active": True,
        },
        {
            "name": "AniWaves",
            "base_url": "https://aniwaves.ru",
            "search_url_template": "https://aniwaves.ru/search?q={query}",
            "episode_pattern": "watch/{slug}/ep-{episode}",
            "priority": 10,
            "is_active": True,
        },
    ]
    for source in sources:
        StreamingSource.objects.update_or_create(name=source["name"], defaults=source)


def unseed_additional_streaming_sources(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    StreamingSource.objects.filter(name__in=["Gogoanime", "AniTaku", "AniWaves"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("streaming", "0002_seed_streaming_sources"),
    ]

    operations = [
        migrations.RunPython(
            seed_additional_streaming_sources,
            reverse_code=unseed_additional_streaming_sources,
        ),
    ]
