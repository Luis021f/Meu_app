from django.db import models


class Produto(models.Model):
    nome = models.CharField(max_length=150)
    imagem = models.FileField(upload_to='produtos/')
    quantidade = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome
