from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("juego", "0002_burbuja_burbujarun_burbujamiembro_burbuja_run_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="burbujarun",
            name="estado",
            field=models.CharField(default="ok", max_length=20),
        ),
    ]
