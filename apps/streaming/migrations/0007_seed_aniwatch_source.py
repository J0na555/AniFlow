from django.db import migrations


def seed_aniwatch_source(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    StreamingSource.objects.update_or_create(
        name="AniWatch",
        defaults={
            "base_url": "https://jp-animenities.com",
            "search_url_template": "https://jp-animenities.com/search/?q={query}",
            "episode_pattern": "title/{slug}",
            "priority": 12,
            "is_active": True,
        },
    )


def unseed_aniwatch_source(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    StreamingSource.objects.filter(name="AniWatch").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("streaming", "0006_disable_non_aniwaves_sources"),
    ]

    operations = [
        migrations.RunPython(
            seed_aniwatch_source,
            reverse_code=unseed_aniwatch_source,
        ),
    ]
