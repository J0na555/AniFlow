from django.db import migrations


def seed_streaming_sources(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    sources = [
        {
            "name": "ExampleStream",
            "base_url": "https://example.com",
            "search_url_template": "https://example.com/search?q={query}",
            "episode_pattern": "/watch/{slug}/episode-{episode}",
            "priority": 100,
            "is_active": True,
        }
    ]
    for source in sources:
        StreamingSource.objects.update_or_create(name=source["name"], defaults=source)


def unseed_streaming_sources(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    StreamingSource.objects.filter(name="ExampleStream").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("streaming", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_streaming_sources, reverse_code=unseed_streaming_sources),
    ]
