from django.db import migrations


def seed_streaming_sources(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    sources = [
        {
            "name": "Crunchyroll",
            "base_url": "https://www.crunchyroll.com",
            "search_url_template": "https://www.crunchyroll.com/search?q={query}",
            "episode_pattern": "",
            "priority": 100,
            "is_active": True,
        }
    ]
    for source in sources:
        StreamingSource.objects.update_or_create(name=source["name"], defaults=source)


def unseed_streaming_sources(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    StreamingSource.objects.filter(name__in=["ExampleStream", "Crunchyroll"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("streaming", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_streaming_sources, reverse_code=unseed_streaming_sources),
    ]
