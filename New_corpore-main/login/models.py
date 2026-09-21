import random
import string
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

def gerador_codigo_mfa():
    """Gera um código MFA numérico com seis posições."""
    return ''.join(random.choices(string.digits, k=6))


class TwoFactorCode(models.Model):
    """Código temporário enviado durante o login em duas etapas."""

    # Excluir o usuário também exclui seus códigos MFA relacionados.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='two_factor_codes')
    # CharField preserva códigos que começam com zero.
    code = models.CharField(max_length=6, default=gerador_codigo_mfa)
    # Define o início da janela de validade do código.
    created_at = models.DateTimeField(auto_now_add=True)
    # Impede que o mesmo código seja aceito mais de uma vez.
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        """Retorna True quando o código não foi usado e ainda não expirou."""
        if self.is_used:
            return False

        # A validade é calculada a partir do horário gravado no banco.
        expiration_time = self.created_at + timedelta(minutes=5)
        return timezone.now() <= expiration_time

    def mark_as_used(self):
        """Invalida o código e atualiza somente o campo alterado."""
        self.is_used = True
        self.save(update_fields=['is_used'])

    def __str__(self):
        """Representação legível para o admin e ferramentas de desenvolvimento."""
        return f"Código 2FA para {self.user} - {self.code}"