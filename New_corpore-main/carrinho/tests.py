import json
import hashlib
import hmac
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from painel.models import Produto

from .models import Pedido
from .views import ErroMercadoPago, normalizar_carrinho


class CarrinhoCheckoutTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='comprador',
			password='senha-de-teste',
		)
		self.client.force_login(self.user)
		self.produto = Produto.objects.create(
			nome='Fonte Mancer',
			categoria='Fontes',
			preco='129.90',
			quantidade=5,
		)

	def assinatura_webhook(self, payment_id, request_id):
		timestamp = '1704908010'
		manifest = f'id:{payment_id};request-id:{request_id};ts:{timestamp};'
		assinatura = hmac.new(
			b'TEST-webhook-secret',
			manifest.encode('utf-8'),
			hashlib.sha256,
		).hexdigest()
		return f'ts={timestamp},v1={assinatura}'

	def test_normaliza_ids_e_agrega_quantidades(self):
		itens = normalizar_carrinho(json.dumps([
			{'id': self.produto.id, 'price': 0.01, 'quantity': 1},
			{'id': self.produto.id, 'price': 0.01, 'quantity': 1},
		]))

		self.assertEqual(itens, [{'produto_id': self.produto.id, 'quantidade': 2}])

	def test_rejeita_produto_desconhecido(self):
		with self.assertRaises(ValueError):
			normalizar_carrinho(json.dumps([
				{'id': 'produto-falso', 'quantity': 1},
			]))

	@override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-token')
	@patch('carrinho.views._chamar_api_mercado_pago')
	def test_checkout_cria_pedido_e_redireciona(self, chamar_api):
		chamar_api.return_value = {
			'id': 'preference-123',
			'init_point': 'https://www.mercadopago.com.br/checkout/test',
		}

		resposta = self.client.post(reverse('iniciar_checkout'), {
			'cart': json.dumps([
				{'id': self.produto.id, 'price': 0.01, 'quantity': 1},
			]),
		})

		pedido = Pedido.objects.get()
		self.assertRedirects(
			resposta,
			'https://www.mercadopago.com.br/checkout/test',
			fetch_redirect_response=False,
		)
		self.assertEqual(pedido.total, Decimal('154.90'))
		self.assertEqual(pedido.preferencia_id, 'preference-123')
		self.assertTrue(pedido.estoque_reservado)
		self.produto.refresh_from_db()
		self.assertEqual(self.produto.quantidade, 4)
		self.assertEqual(chamar_api.call_args.args[:2], (
			'POST', '/checkout/preferences'
		))
		self.assertEqual(
			chamar_api.call_args.args[2]['items'][0]['unit_price'],
			129.9,
		)

	@override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-token')
	@patch('carrinho.views._chamar_api_mercado_pago')
	def test_checkout_exige_login(self, chamar_api):
		self.client.logout()

		resposta = self.client.post(reverse('iniciar_checkout'), {
			'cart': json.dumps([
				{'id': self.produto.id, 'quantity': 1},
			]),
		})

		self.assertRedirects(
			resposta,
			f"{reverse('login')}?next={reverse('iniciar_checkout')}",
		)
		self.assertEqual(Pedido.objects.count(), 0)
		self.produto.refresh_from_db()
		self.assertEqual(self.produto.quantidade, 5)
		chamar_api.assert_not_called()

	@override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-token')
	@patch('carrinho.views._chamar_api_mercado_pago')
	def test_checkout_rejeita_quantidade_acima_do_estoque(self, chamar_api):
		resposta = self.client.post(reverse('iniciar_checkout'), {
			'cart': json.dumps([
				{'id': self.produto.id, 'quantity': 6},
			]),
		})

		self.assertRedirects(resposta, reverse('carrinho'))
		self.assertEqual(Pedido.objects.count(), 0)
		self.produto.refresh_from_db()
		self.assertEqual(self.produto.quantidade, 5)
		chamar_api.assert_not_called()

	@override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-token')
	@patch('carrinho.views._chamar_api_mercado_pago')
	def test_falha_ao_criar_pagamento_devolve_estoque(self, chamar_api):
		chamar_api.side_effect = ErroMercadoPago('falha de teste')

		resposta = self.client.post(reverse('iniciar_checkout'), {
			'cart': json.dumps([
				{'id': self.produto.id, 'quantity': 2},
			]),
		})

		pedido = Pedido.objects.get()
		self.assertRedirects(resposta, reverse('carrinho'))
		self.assertEqual(pedido.status, Pedido.Status.FALHOU)
		self.assertFalse(pedido.estoque_reservado)
		self.produto.refresh_from_db()
		self.assertEqual(self.produto.quantidade, 5)

	@override_settings(
		MERCADOPAGO_ACCESS_TOKEN='TEST-token',
		MERCADOPAGO_WEBHOOK_SECRET='TEST-webhook-secret',
	)
	@patch('carrinho.views._chamar_api_mercado_pago')
	def test_webhook_cancelado_devolve_estoque_uma_unica_vez(self, chamar_api):
		Produto.objects.filter(pk=self.produto.pk).update(quantidade=4)
		pedido = Pedido.objects.create(
			itens=[{
				'produto_id': self.produto.id,
				'nome': self.produto.nome,
				'quantidade': 1,
				'preco_unitario': '129.90',
			}],
			subtotal='129.90',
			frete='25.00',
			total='154.90',
			status=Pedido.Status.PENDENTE,
			estoque_reservado=True,
		)
		chamar_api.return_value = {
			'id': 12345,
			'external_reference': str(pedido.pk),
			'currency_id': 'BRL',
			'transaction_amount': 154.90,
			'status': 'cancelled',
		}
		url = reverse('webhook_mercado_pago') + '?data.id=12345'
		headers = {
			'HTTP_X_SIGNATURE': self.assinatura_webhook('12345', 'request-cancel'),
			'HTTP_X_REQUEST_ID': 'request-cancel',
		}

		self.assertEqual(self.client.post(url, **headers).status_code, 200)
		self.assertEqual(self.client.post(url, **headers).status_code, 200)
		self.produto.refresh_from_db()
		pedido.refresh_from_db()
		self.assertEqual(self.produto.quantidade, 5)
		self.assertFalse(pedido.estoque_reservado)

	@override_settings(
		MERCADOPAGO_ACCESS_TOKEN='TEST-token',
		MERCADOPAGO_WEBHOOK_SECRET='TEST-webhook-secret',
	)
	@patch('carrinho.views._chamar_api_mercado_pago')
	def test_webhook_confirma_pagamento_consultado(self, chamar_api):
		pedido = Pedido.objects.create(
			itens=[{'nome': 'Camiseta Atlas', 'quantidade': 1}],
			subtotal='129.90',
			frete='25.00',
			total='154.90',
			status=Pedido.Status.PENDENTE,
		)
		chamar_api.return_value = {
			'id': 12345,
			'external_reference': str(pedido.pk),
			'currency_id': 'BRL',
			'transaction_amount': 154.90,
			'status': 'approved',
		}

		resposta = self.client.post(
			reverse('webhook_mercado_pago') + '?data.id=12345',
			HTTP_X_SIGNATURE=self.assinatura_webhook('12345', 'request-123'),
			HTTP_X_REQUEST_ID='request-123',
		)

		pedido.refresh_from_db()
		self.assertEqual(resposta.status_code, 200)
		self.assertEqual(pedido.status, Pedido.Status.APROVADO)
		self.assertEqual(pedido.pagamento_id, '12345')

	@override_settings(
		MERCADOPAGO_ACCESS_TOKEN='TEST-token',
		MERCADOPAGO_WEBHOOK_SECRET='TEST-webhook-secret',
	)
	@patch('carrinho.views._chamar_api_mercado_pago')
	def test_webhook_ignora_referencia_externa_invalida(self, chamar_api):
		chamar_api.return_value = {
			'id': 12345,
			'external_reference': 'referencia-invalida',
			'currency_id': 'BRL',
			'transaction_amount': 154.90,
			'status': 'approved',
		}

		resposta = self.client.post(
			reverse('webhook_mercado_pago') + '?data.id=12345',
			HTTP_X_SIGNATURE=self.assinatura_webhook('12345', 'request-456'),
			HTTP_X_REQUEST_ID='request-456',
		)

		self.assertEqual(resposta.status_code, 200)
		self.assertEqual(Pedido.objects.count(), 0)

	@override_settings(
		MERCADOPAGO_ACCESS_TOKEN='TEST-token',
		MERCADOPAGO_WEBHOOK_SECRET='TEST-webhook-secret',
	)
	@patch('carrinho.views._chamar_api_mercado_pago')
	def test_webhook_rejeita_assinatura_invalida(self, chamar_api):
		resposta = self.client.post(
			reverse('webhook_mercado_pago') + '?data.id=12345',
			HTTP_X_SIGNATURE='ts=1,v1=invalid',
			HTTP_X_REQUEST_ID='request-789',
		)

		self.assertEqual(resposta.status_code, 401)
		chamar_api.assert_not_called()
