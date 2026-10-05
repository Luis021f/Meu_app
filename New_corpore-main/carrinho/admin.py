from django.contrib import admin
from .models import Pedido


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
	list_display = ('id', 'status', 'total', 'pagamento_id', 'criado_em')
	list_filter = ('status', 'criado_em')
	readonly_fields = (
		'id', 'itens', 'subtotal', 'frete', 'total', 'status',
		'preferencia_id', 'pagamento_id', 'criado_em',
	)
