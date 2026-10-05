import uuid

from django.db import models


class Pedido(models.Model):
	class Status(models.TextChoices):
		CRIADO = 'created', 'Criado'
		PENDENTE = 'pending', 'Pendente'
		APROVADO = 'approved', 'Aprovado'
		RECUSADO = 'rejected', 'Recusado'
		CANCELADO = 'cancelled', 'Cancelado'
		REEMBOLSADO = 'refunded', 'Reembolsado'
		CONTESTADO = 'charged_back', 'Contestado'
		FALHOU = 'failed', 'Falhou'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	itens = models.JSONField()
	subtotal = models.DecimalField(max_digits=10, decimal_places=2)
	frete = models.DecimalField(max_digits=10, decimal_places=2)
	total = models.DecimalField(max_digits=10, decimal_places=2)
	estoque_reservado = models.BooleanField(default=False)
	status = models.CharField(
		max_length=20,
		choices=Status.choices,
		default=Status.CRIADO,
	)
	preferencia_id = models.CharField(max_length=100, blank=True)
	pagamento_id = models.CharField(max_length=100, blank=True)
	criado_em = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-criado_em']

	def __str__(self):
		return f'Pedido {self.pk} ({self.get_status_display()})'
