from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProdutoForm
from .models import Produto

@login_required(login_url='login')
def painel(request):
    produtos = Produto.objects.all()
    return render(request, 'painel/painel.html', {'produtos': produtos})


@login_required(login_url='login')
def cad_prod(request):
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produto cadastrado com sucesso.')
            return redirect('painel')
    else:
        form = ProdutoForm()
    return render(request, 'cad_prod/cad_prod.html', {'form': form, 'modo': 'Cadastrar'})


@login_required(login_url='login')
def editar_produto(request, produto_id):
    produto = get_object_or_404(Produto, pk=produto_id)
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES, instance=produto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produto atualizado com sucesso.')
            return redirect('painel')
    else:
        form = ProdutoForm(instance=produto)
    return render(request, 'cad_prod/cad_prod.html', {'form': form, 'modo': 'Editar', 'produto': produto})


@login_required(login_url='login')
def excluir_produto(request, produto_id):
    produto = get_object_or_404(Produto, pk=produto_id)
    if request.method == 'POST':
        produto.delete()
        messages.success(request, 'Produto excluído do estoque.')
    return redirect('painel')

# Create your views here.