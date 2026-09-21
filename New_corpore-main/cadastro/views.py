from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
import uuid

def cadastro(request):
    if request.method == "POST":
        # Captura os dados do formulário em variáveis simples
        username = request.POST.get("usuario")
        email = request.POST.get("email")
        senha = request.POST.get("senha")
        confirmar_senha = request.POST.get("confirmar_senha")

        # --- VALIDAÇÕES ---

        # 1. Verifica se as senhas coincidem
        if senha != confirmar_senha:
            messages.error(request, "As senhas não coincidem.")
            return render(request, "cadastro/cadastro.html")

        # 2. Verifica se a senha tem pelo menos 8 caracteres
        if len(senha) < 8:
            messages.error(
                request, "A senha deve ter pelo menos 8 caracteres."
            )
            return render(request, "cadastro/cadastro.html")

        # 3. Verifica se o E-MAIL já está cadastrado
        if User.objects.filter(email=email).exists():
            messages.error(request, "Este e-mail já está cadastrado.")
            return render(request, "cadastro/cadastro.html")

        # --- CRIAÇÃO DO USUÁRIO ---

        # Gera um username aleatório único de 30 caracteres para o Django aceitar no banco
        username_unico = uuid.uuid4().hex[:30]

        # Cria o usuário desativado salvando o nome real no campo first_name
        user = User.objects.create_user(
            username=username_unico,
            email=email,
            password=senha,
            first_name=username,
            is_active=False,
        )

        # --- ENVIO DO LINK DE ATIVAÇÃO ---

        # 1. Gera os tokens para o link de confirmação
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # 2. Monta o link absoluto de ativação
        relative_link = reverse(
            "ativar_conta", kwargs={"uidb64": uid, "token": token}
        )
        domain = get_current_site(request).domain
        activation_url = f"http://difusao.tech{relative_link}"

        # 3. Envia o e-mail via SMTP
        assunto = "Confirme seu e-mail de cadastro"
        mensagem = (
            f"Olá, {user.first_name}!\n\n"
            f"Por favor, clique no link abaixo para ativar sua conta:\n\n"
            f"{activation_url}\n\n"
            f"Se você não solicitou este cadastro, ignore este e-mail."
        )

        send_mail(assunto, mensagem, None, [user.email], fail_silently=False)

        messages.success(
            request,
            "Cadastro realizado! Enviamos um link de ativação para o seu e-mail.",
        )
        return redirect("login")

    return render(request, "cadastro/cadastro.html")





# 4. View para processar o clique no link de confirmação
def ativar_conta(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Sua conta foi ativada com sucesso! Você já pode fazer login.')
    else:
        messages.error(request, 'O link de ativação é inválido ou expirou.')

    return redirect('login')