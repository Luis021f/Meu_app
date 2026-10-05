from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Produto(models.Model):
    nome = models.CharField(max_length=150)
    categoria = models.CharField(max_length=80, default='Geral')
    preco = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    imagem = models.FileField(upload_to='produtos/')
    quantidade = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Adicionado em')

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome
