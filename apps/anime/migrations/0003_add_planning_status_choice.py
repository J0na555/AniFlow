from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("anime", "0002_alter_useranime_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="useranime",
            name="status",
            field=models.CharField(
                choices=[
                    ("watching", "Watching"),
                    ("planning", "Planning"),
                    ("completed", "Completed"),
                    ("dropped", "Dropped"),
                    ("paused", "Paused"),
                    ("repeating", "Repeating"),
                ],
                default="planning",
                max_length=16,
            ),
        ),
    ]
