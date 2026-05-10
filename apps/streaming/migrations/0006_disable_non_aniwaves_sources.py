from django.db import migrations


NON_ANIWAVES_SOURCE_NAMES = ["Crunchyroll", "Gogoanime", "AniTaku"]


def disable_non_aniwaves_sources(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    StreamingSource.objects.filter(name__in=NON_ANIWAVES_SOURCE_NAMES).update(is_active=False)


def enable_non_aniwaves_sources(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    StreamingSource.objects.filter(name__in=NON_ANIWAVES_SOURCE_NAMES).update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("streaming", "0005_update_aniwaves_search_template"),
    ]

    operations = [
        migrations.RunPython(
            disable_non_aniwaves_sources,
            reverse_code=enable_non_aniwaves_sources,
        ),
    ]
