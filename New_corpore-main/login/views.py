from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.utils.http import url_has_allowed_host_and_scheme
# Limita a view aos métodos HTTP usados pelo formulário de login.
from django.views.decorators.http import require_http_methods
# Recursos necessários para enviar o código MFA por e-mail.
from django.core.mail import send_mail
from .models import TwoFactorCode
from painel.permissions import pode_gerenciar_produtos

@require_http_methods(["GET", "POST"])
def login_view(request):
    """Valida a senha e inicia a segunda etapa da autenticação."""
    if request.method == 'GET':
        next_url = request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            request.session['login_next'] = next_url
        else:
            request.session.pop('login_next', None)

    if request.method == 'POST':
        # Lê as credenciais enviadas pelo formulário.
        email = request.POST.get('email', '').strip().lower()
        senha = request.POST.get('senha')

        # O backend padrão autentica por username; primeiro localizamos esse valor pelo e-mail.
        usuario_objeto = User.objects.filter(email=email).first()

        if usuario_objeto:
            # A autenticação também verifica a senha e se a conta está ativa.
            user = authenticate(request, username=usuario_objeto.username, password=senha)

            if user is not None:
                # Apenas o código mais recente deve permanecer utilizável.
                TwoFactorCode.objects.filter(user=user, is_used=False).update(is_used=True)

                # Cria um código de seis dígitos com validade limitada.
                two_factor_obj = TwoFactorCode.objects.create(user=user)

                send_mail(
                    subject='Seu código de autenticação',
                    message=f'Seu código de acesso de 6 dígitos é: {two_factor_obj.code}. Ele é válido por 5 minutos.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

                # Guarda o ID necessário para a view MFA concluir o login.
                request.session['pre_2fa_user_id'] = user.id
                return redirect('mfa')


            # Informa que falta ativar a conta sem expor dados a terceiros.
            if not usuario_objeto.is_active and usuario_objeto.check_password(senha):
                messages.error(request,"Sua conta ainda não foi ativada. Verifique seu e-mail.")
                return render(request, "login/login.html")

        # Uma mensagem única evita revelar se o e-mail existe no sistema.
        messages.error(request, "E-mail ou senha inválidos.")

    # GET e falhas de validação retornam o formulário de login.
    return render(request, 'login/login.html')



def mfa_view(request):
    """Valida o código MFA e efetiva o login após a senha ser aceita."""
    user_id = request.session.get('pre_2fa_user_id')
    
    # Sem o ID temporário, a primeira etapa do login não foi concluída.
    if not user_id:
        return redirect('login')

    if request.method == 'POST':
        # Texto preserva zeros à esquerda do código.
        code_input = request.POST.get('code')
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            # A sessão pode apontar para um usuário que foi removido.
            request.session.pop('pre_2fa_user_id', None)
            return redirect('login')

        with transaction.atomic():
            two_factor_obj = TwoFactorCode.objects.select_for_update().filter(
                user=user,
                code=code_input,
                is_used=False,
            ).order_by('-created_at').first()

            if two_factor_obj and two_factor_obj.is_valid() and user.is_active:
                two_factor_obj.mark_as_used()
                login(request, user)
                request.session.pop('pre_2fa_user_id', None)
                next_url = request.session.pop('login_next', None)
                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)
                if pode_gerenciar_produtos(user):
                    return redirect('painel')
                return redirect('home')

            messages.error(request, 'Código inválido ou expirado.')

    # Exibe o formulário tanto no primeiro acesso quanto após um erro.
    return render(
        request,
        'login/mfa.html',
        {'codigo_no_terminal': settings.DEBUG},
    )


def logout_view(request):
    """Encerra a sessão atual e volta para a página inicial."""
    logout(request)
    return redirect('home')