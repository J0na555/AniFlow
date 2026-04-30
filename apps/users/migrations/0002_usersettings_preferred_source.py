from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("streaming", "0001_initial"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="preferred_source",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="preferred_by_users",
                to="streaming.streamingsource",
            ),
        ),
    ]
