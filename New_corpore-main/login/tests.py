from datetime import timedelta
from contextlib import redirect_stdout
from io import StringIO

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import TwoFactorCode


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LoginMfaTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='maria-interno',
			email='maria@example.com',
			password='senha-segura-123',
			is_active=True,
		)

	@override_settings(
		DEBUG=True,
		EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
	)
	def test_login_normaliza_email_e_exibe_codigo_no_terminal(self):
		terminal = StringIO()
		with redirect_stdout(terminal):
			response = self.client.post(reverse('login'), {
				'email': ' MARIA@EXAMPLE.COM ',
				'senha': 'senha-segura-123',
			})

		self.assertRedirects(response, reverse('mfa'))
		self.assertFalse(response.wsgi_request.user.is_authenticated)
		codigo = TwoFactorCode.objects.get(user=self.user)
		self.assertIn(codigo.code, terminal.getvalue())
		self.assertEqual(mail.outbox, [])
		self.assertContains(self.client.get(reverse('mfa')), 'terminal do servidor')

		response = self.client.post(reverse('mfa'), {'code': codigo.code})

		self.assertRedirects(
			response,
			reverse('home'),
			fetch_redirect_response=False,
		)
		self.assertTrue(response.wsgi_request.user.is_authenticated)
		codigo.refresh_from_db()
		self.assertTrue(codigo.is_used)

		self.client.logout()
		session = self.client.session
		session['pre_2fa_user_id'] = self.user.id
		session.save()
		response = self.client.post(reverse('mfa'), {'code': codigo.code})

		self.assertEqual(response.status_code, 200)
		self.assertFalse(response.wsgi_request.user.is_authenticated)

	@override_settings(DEBUG=False, DEFAULT_FROM_EMAIL='loja@example.com')
	def test_login_em_producao_envia_codigo_por_email(self):
		response = self.client.post(reverse('login'), {
			'email': self.user.email,
			'senha': 'senha-segura-123',
		})

		self.assertRedirects(response, reverse('mfa'))
		codigo = TwoFactorCode.objects.get(user=self.user)
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn(codigo.code, mail.outbox[0].body)
		self.assertContains(self.client.get(reverse('mfa')), 'para o seu e-mail')

	def test_usuario_staff_e_redirecionado_para_painel(self):
		self.user.is_staff = True
		self.user.save(update_fields=['is_staff'])
		self.client.post(reverse('login'), {
			'email': self.user.email,
			'senha': 'senha-segura-123',
		})
		codigo = TwoFactorCode.objects.get(user=self.user)

		response = self.client.post(reverse('mfa'), {'code': codigo.code})

		self.assertRedirects(
			response,
			reverse('painel'),
			fetch_redirect_response=False,
		)

	def test_login_retorna_para_destino_local_apos_mfa(self):
		destino = reverse('iniciar_checkout')
		self.client.get(reverse('login'), {'next': destino})
		self.client.post(reverse('login'), {
			'email': self.user.email,
			'senha': 'senha-segura-123',
		})
		codigo = TwoFactorCode.objects.get(user=self.user)

		response = self.client.post(reverse('mfa'), {'code': codigo.code})

		self.assertRedirects(response, destino, fetch_redirect_response=False)

	def test_codigo_expirado_e_rejeitado(self):
		self.client.post(reverse('login'), {
			'email': self.user.email,
			'senha': 'senha-segura-123',
		})
		codigo = TwoFactorCode.objects.get(user=self.user)
		TwoFactorCode.objects.filter(pk=codigo.pk).update(
			created_at=timezone.now() - timedelta(minutes=6)
		)

		response = self.client.post(reverse('mfa'), {'code': codigo.code})

		self.assertEqual(response.status_code, 200)
		self.assertFalse(response.wsgi_request.user.is_authenticated)

	def test_conta_inativa_nao_recebe_codigo(self):
		self.user.is_active = False
		self.user.save(update_fields=['is_active'])

		response = self.client.post(reverse('login'), {
			'email': self.user.email,
			'senha': 'senha-segura-123',
		})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(mail.outbox, [])
		self.assertFalse(TwoFactorCode.objects.filter(user=self.user).exists())
