from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ProdutoForm
from .models import Produto


class ProdutoEditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='12345678')
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.produto = Produto.objects.create(
            id=1,
            nome='Teclado Mecânico',
            categoria='Periféricos',
            preco='299.90',
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
                'categoria': 'Periféricos',
                'preco': '349.90',
                'quantidade': 15,
            },
            follow=True,
        )

        self.produto.refresh_from_db()

        self.assertRedirects(response, reverse('painel'))
        self.assertEqual(self.produto.id, 1)
        self.assertEqual(self.produto.nome, 'Teclado Mecânico Pro')
        self.assertEqual(str(self.produto.preco), '349.90')
        self.assertEqual(self.produto.quantidade, 15)

    def test_cadastrar_produto_sem_id_gera_id_automatico(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('cad_prod'),
            {
                'nome': 'Monitor UltraWide',
                'categoria': 'Monitores',
                'preco': '1599.90',
                'quantidade': 7,
                'imagem': SimpleUploadedFile('monitor.png', b'conteudo', content_type='image/png'),
            },
            follow=True,
        )

        produto = Produto.objects.get(nome='Monitor UltraWide')

        self.assertRedirects(response, reverse('painel'))
        self.assertIsNotNone(produto.id)
        self.assertEqual(produto.quantidade, 7)

    def test_usuario_comum_nao_acessa_painel_de_produtos(self):
        cliente = User.objects.create_user(
            username='cliente',
            password='senha-segura-123',
        )
        self.client.force_login(cliente)

        respostas = (
            self.client.get(reverse('painel')),
            self.client.get(reverse('cad_prod')),
            self.client.get(reverse('editar_produto', args=[self.produto.id])),
            self.client.post(reverse('excluir_produto', args=[self.produto.id])),
        )

        self.assertTrue(all(resposta.status_code == 403 for resposta in respostas))
        self.assertTrue(Produto.objects.filter(pk=self.produto.pk).exists())

    def test_gerencia_geral_pode_acessar_painel(self):
        gerente = User.objects.create_user(
            username='user_gerencia_geral',
            password='senha-segura-123',
        )
        grupo, _ = Group.objects.get_or_create(name='Gerencia Geral')
        gerente.groups.add(grupo)
        self.client.force_login(gerente)

        resposta = self.client.get(reverse('painel'))

        self.assertEqual(resposta.status_code, 200)

    def test_painel_exibe_data_e_horario_de_cadastro(self):
        self.client.force_login(self.user)

        resposta = self.client.get(reverse('painel'))
        horario = timezone.localtime(self.produto.criado_em).strftime('%d/%m/%Y %H:%M')

        self.assertContains(resposta, 'Adicionado em')
        self.assertContains(resposta, horario)
