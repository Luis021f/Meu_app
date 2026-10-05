import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('painel', '0004_assign_gerencia_geral_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='produto',
            name='criado_em',
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name='Adicionado em',
            ),
            preserve_default=False,
        ),
    ]