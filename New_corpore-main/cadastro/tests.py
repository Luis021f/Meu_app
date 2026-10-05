from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


class CadastroTests(TestCase):
	@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
	def test_registration_sends_activation_email(self):
		response = self.client.post(
			reverse('cadastro'),
			{
				'usuario': 'Test User',
				'email': 'test@example.com',
				'senha': 'strong-password-123',
				'confirmar_senha': 'strong-password-123',
			},
		)

		self.assertRedirects(response, reverse('login'))
		user = User.objects.get(email='test@example.com')
		self.assertFalse(user.is_active)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)
		self.assertIn('/ativar/', mail.outbox[0].body)

	@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
	@override_settings(ALLOWED_HOSTS=['loja.test'])
	def test_email_e_normalizado_e_link_usa_host_da_requisicao(self):
		response = self.client.post(
			reverse('cadastro'),
			{
				'usuario': 'Maria Silva',
				'email': ' MARIA@EXAMPLE.COM ',
				'senha': 'senha-segura-123',
				'confirmar_senha': 'senha-segura-123',
			},
			HTTP_HOST='loja.test',
		)

		self.assertRedirects(response, reverse('login'))
		self.assertTrue(User.objects.filter(email='maria@example.com').exists())
		self.assertIn('http://loja.test/ativar/', mail.outbox[0].body)

	@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
	def test_cadastro_rejeita_campos_obrigatorios_vazios(self):
		response = self.client.post(
			reverse('cadastro'),
			{
				'usuario': '',
				'email': '',
				'senha': '',
				'confirmar_senha': '',
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertFalse(User.objects.exists())
		self.assertEqual(mail.outbox, [])
