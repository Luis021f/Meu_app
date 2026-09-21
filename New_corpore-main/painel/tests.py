from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .forms import ProdutoForm
from .models import Produto


class ProdutoEditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='12345678')
        self.produto = Produto.objects.create(
            id=1,
            nome='Teclado Mecânico',
            imagem=SimpleUploadedFile('teclado.png', b'conteudo', content_type='image/png'),
            quantidade=10,
        )

    def test_formulario_nao_exibe_o_campo_id(self):
        form = ProdutoForm()
        self.assertNotIn('id', form.fields)

    def test_editar_produto_atualiza_dados_sem_alterar_id(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('editar_produto', args=[self.produto.id]),
            {
                'nome': 'Teclado Mecânico Pro',
                'quantidade': 15,
            },
            follow=True,
        )

        self.produto.refresh_from_db()

        self.assertRedirects(response, reverse('painel'))
        self.assertEqual(self.produto.id, 1)
        self.assertEqual(self.produto.nome, 'Teclado Mecânico Pro')
        self.assertEqual(self.produto.quantidade, 15)

    def test_cadastrar_produto_sem_id_gera_id_automatico(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('cad_prod'),
            {
                'nome': 'Monitor UltraWide',
                'quantidade': 7,
                'imagem': SimpleUploadedFile('monitor.png', b'conteudo', content_type='image/png'),
            },
            follow=True,
        )

        produto = Produto.objects.get(nome='Monitor UltraWide')

        self.assertRedirects(response, reverse('painel'))
        self.assertIsNotNone(produto.id)
        self.assertEqual(produto.quantidade, 7)
