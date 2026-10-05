from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from painel.models import Produto


class CatalogTests(TestCase):
	def setUp(self):
		self.produto = Produto.objects.create(
			nome='Fonte Mancer 650W',
			categoria='Fontes',
			preco='249.90',
			quantidade=4,
		)

	def test_home_lista_produtos_do_banco(self):
		resposta = self.client.get(reverse('home'))

		self.assertEqual(resposta.status_code, 200)
		self.assertContains(resposta, 'Fonte Mancer 650W')
		self.assertContains(resposta, 'R$ 249,90')
		self.assertContains(resposta, f'data-product-id="{self.produto.id}"')
		self.assertContains(resposta, reverse('login'))

	def test_home_mostra_conta_logada_e_opcao_de_sair(self):
		usuario = User.objects.create_user(
			username='cliente',
			email='cliente@example.com',
			password='senha-segura-123',
		)
		self.client.force_login(usuario)

		resposta = self.client.get(reverse('home'))

		self.assertContains(resposta, 'Conectado: cliente@example.com')
		self.assertContains(resposta, reverse('logout'))
		self.assertContains(resposta, 'Sair')

	def test_categoria_mostra_produtos_da_categoria(self):
		resposta = self.client.get(
			reverse('categoria_produtos', args=['fontes'])
		)

		self.assertEqual(resposta.status_code, 200)
		self.assertContains(resposta, 'Fontes')
		self.assertContains(resposta, 'Fonte Mancer 650W')
		self.assertContains(resposta, f'data-id="{self.produto.id}"')
