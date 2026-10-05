from itertools import groupby

from django.http import Http404
from django.shortcuts import render
from django.utils.text import slugify

from painel.models import Produto

# Create your views here.
def home(request):
    produtos = Produto.objects.filter(
        quantidade__gt=0,
        preco__gt=0,
    ).order_by('categoria', 'nome')
    categorias = [
        {
            'nome': categoria,
            'slug': slugify(categoria),
            'produtos': list(itens),
        }
        for categoria, itens in groupby(produtos, key=lambda produto: produto.categoria)
    ]
    return render(request, 'home/home.html', {'categorias': categorias})


def categoria_produtos(request, categoria_slug):
    nomes = Produto.objects.order_by('categoria').values_list(
        'categoria', flat=True
    ).distinct()
    categoria = next(
        (nome for nome in nomes if slugify(nome) == categoria_slug),
        None,
    )
    if categoria is None:
        raise Http404

    produtos = Produto.objects.filter(
        categoria=categoria,
        quantidade__gt=0,
        preco__gt=0,
    ).order_by('nome')
    return render(
        request,
        'home/categoria.html',
        {'categoria': categoria, 'produtos': produtos},
    )