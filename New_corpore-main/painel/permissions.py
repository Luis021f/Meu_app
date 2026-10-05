GRUPO_GERENCIA_GERAL = 'Gerencia Geral'


def pode_gerenciar_produtos(user):
    return bool(
        user.is_authenticated
        and (
            user.is_staff
            or user.is_superuser
            or user.groups.filter(name=GRUPO_GERENCIA_GERAL).exists()
        )
    )
