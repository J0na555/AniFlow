from django.db import migrations


def update_aniwaves_search_template(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    StreamingSource.objects.filter(name="AniWaves").update(
        search_url_template="https://aniwaves.ru/filter?keyword={query}"
    )


def rollback_aniwaves_search_template(apps, schema_editor) -> None:
    StreamingSource = apps.get_model("streaming", "StreamingSource")
    StreamingSource.objects.filter(name="AniWaves").update(
        search_url_template="https://aniwaves.ru/search?q={query}"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("streaming", "0004_seed_aniwaves_source"),
    ]

    operations = [
        migrations.RunPython(
            update_aniwaves_search_template,
            reverse_code=rollback_aniwaves_search_template,
        ),
    ]
