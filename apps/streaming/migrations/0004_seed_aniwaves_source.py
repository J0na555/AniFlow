from django.db import migrations


def seed_aniwaves_source(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    StreamingSource.objects.update_or_create(
        name="AniWaves",
        defaults={
            "base_url": "https://aniwaves.ru",
            "search_url_template": "https://aniwaves.ru/search?q={query}",
            "episode_pattern": "watch/{slug}",
            "priority": 10,
            "is_active": True,
        },
    )


def unseed_aniwaves_source(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    StreamingSource.objects.filter(name="AniWaves").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("streaming", "0003_seed_additional_streaming_sources"),
    ]

    operations = [
        migrations.RunPython(
            seed_aniwaves_source,
            reverse_code=unseed_aniwaves_source,
        ),
    ]
