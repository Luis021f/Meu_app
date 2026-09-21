"""
URL configuration for loja project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from carrinho import views as carrinho_views
from app import views as app_views
from login import views as login_views
from cadastro import views as cadastro_views
from painel import views as painel_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('carrinho/', carrinho_views.carrinho, name='carrinho'),
    path('home/', app_views.home, name='home'),
    path('', app_views.home, name='home'),
    path('login/', login_views.login_view, name='login'),
    path('login/mfa/', login_views.mfa_view, name='mfa'),
    path('logout/', login_views.logout_view, name='logout'),
    path('cadastro/', cadastro_views.cadastro, name='cadastro'),
    path('ativar/<uidb64>/<token>/', cadastro_views.ativar_conta, name='ativar_conta'),
    path('painel/', painel_views.painel, name='painel'),
    path('painel/cad-prod/', painel_views.cad_prod, name='cad_prod'),
    path('painel/produto/<int:produto_id>/editar/', painel_views.editar_produto, name='editar_produto'),
    path('painel/produto/<int:produto_id>/excluir/', painel_views.excluir_produto, name='excluir_produto'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
