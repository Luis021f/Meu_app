from django.conf import settings
from django.db import migrations


GROUP_NAME = 'Gerencia Geral'


def add_manager_group(apps, schema_editor):
    database = schema_editor.connection.alias
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    group, _ = Group.objects.using(database).get_or_create(name=GROUP_NAME)
    user = User.objects.using(database).filter(
        username='user_gerencia_geral'
    ).first()
    if user:
        through = User.groups.through
        through.objects.using(database).get_or_create(
            user_id=user.pk,
            group_id=group.pk,
        )


def remove_manager_group(apps, schema_editor):
    database = schema_editor.connection.alias
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    group = Group.objects.using(database).filter(name=GROUP_NAME).first()
    user = User.objects.using(database).filter(
        username='user_gerencia_geral'
    ).first()
    if group and user:
        User.groups.through.objects.using(database).filter(
            user_id=user.pk,
            group_id=group.pk,
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('painel', '0003_produto_categoria_produto_preco'),
    ]

    operations = [
        migrations.RunPython(add_manager_group, remove_manager_group),
    ]
