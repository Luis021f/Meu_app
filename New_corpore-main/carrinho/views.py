import hashlib
import hmac
import json
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from painel.models import Produto

from .models import Pedido


FRETE_PADRAO = Decimal('25.00')
FRETE_GRATIS_A_PARTIR_DE = Decimal('300.00')
MERCADOPAGO_API = 'https://api.mercadopago.com'


class ErroMercadoPago(Exception):
    pass


def normalizar_carrinho(dados):
    try:
        carrinho = json.loads(dados)
    except (TypeError, json.JSONDecodeError) as erro:
        raise ValueError('O carrinho enviado é inválido.') from erro

    if not isinstance(carrinho, list) or not carrinho or len(carrinho) > 50:
        raise ValueError('Adicione produtos ao carrinho antes de continuar.')

    quantidades = {}
    for item in carrinho:
        if not isinstance(item, dict):
            raise ValueError('O carrinho contém um produto inválido.')
        produto_id = item.get('id')
        if (
            isinstance(produto_id, bool)
            or not isinstance(produto_id, int)
            or produto_id < 1
        ):
            raise ValueError('O carrinho contém um produto inválido.')
        quantidade = item.get('quantity')
        if isinstance(quantidade, bool) or not isinstance(quantidade, int):
            raise ValueError('A quantidade de um produto é inválida.')
        quantidades[produto_id] = quantidades.get(produto_id, 0) + quantidade
        if quantidade < 1 or quantidades[produto_id] > 99:
            raise ValueError('A quantidade máxima por produto é 99.')

    return [
        {'produto_id': produto_id, 'quantidade': quantidade}
        for produto_id, quantidade in quantidades.items()
    ]


def _chamar_api_mercado_pago(metodo, caminho, dados=None):
    token = settings.MERCADOPAGO_ACCESS_TOKEN
    corpo = json.dumps(dados).encode('utf-8') if dados is not None else None
    requisicao = Request(
        f'{MERCADOPAGO_API}{caminho}',
        data=corpo,
        method=metodo,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
    )
    try:
        with urlopen(requisicao, timeout=15) as resposta:
            return json.loads(resposta.read().decode('utf-8'))
    except HTTPError as erro:
        raise ErroMercadoPago('O Mercado Pago não aceitou a solicitação.') from erro
    except (URLError, TimeoutError, json.JSONDecodeError) as erro:
        raise ErroMercadoPago('Não foi possível conectar ao Mercado Pago.') from erro


def _criar_preferencia(pedido):
    itens = [
        {
            'title': item['nome'],
            'quantity': item['quantidade'],
            'currency_id': 'BRL',
            'unit_price': float(item['preco_unitario']),
        }
        for item in pedido.itens
    ]
    if pedido.frete:
        itens.append({
            'title': 'Frete',
            'quantity': 1,
            'currency_id': 'BRL',
            'unit_price': float(pedido.frete),
        })

    dados = {
        'items': itens,
        'external_reference': str(pedido.pk),
    }
    site_url = settings.MERCADOPAGO_SITE_URL.rstrip('/')
    if site_url:
        url_retorno = (
            f'{site_url}{reverse("resultado_checkout")}?'
            f'{urlencode({"pedido": pedido.pk})}'
        )
        dados['back_urls'] = {
            'success': url_retorno,
            'pending': url_retorno,
            'failure': url_retorno,
        }
        dados['auto_return'] = 'approved'

    if settings.MERCADOPAGO_WEBHOOK_URL:
        dados['notification_url'] = settings.MERCADOPAGO_WEBHOOK_URL

    preferencia = _chamar_api_mercado_pago(
        'POST', '/checkout/preferences', dados
    )
    url_checkout = preferencia.get('init_point') or preferencia.get(
        'sandbox_init_point'
    )
    if not preferencia.get('id') or not url_checkout:
        raise ErroMercadoPago('O Mercado Pago retornou uma preferência incompleta.')
    return preferencia['id'], url_checkout


def _assinatura_webhook_valida(request, pagamento_id):
    segredo = settings.MERCADOPAGO_WEBHOOK_SECRET
    assinatura = request.headers.get('x-signature', '')
    request_id = request.headers.get('x-request-id', '')
    if not segredo or not assinatura or not request_id:
        return False

    partes = {}
    for parte in assinatura.split(','):
        chave, separador, valor = parte.strip().partition('=')
        if separador:
            partes[chave] = valor
    timestamp = partes.get('ts')
    assinatura_recebida = partes.get('v1')
    if not timestamp or not assinatura_recebida:
        return False

    manifest = (
        f'id:{str(pagamento_id).lower()};'
        f'request-id:{request_id};'
        f'ts:{timestamp};'
    )
    assinatura_esperada = hmac.new(
        segredo.encode('utf-8'),
        manifest.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(assinatura_esperada, assinatura_recebida)


def _liberar_estoque(pedido):
    with transaction.atomic():
        pedido_bloqueado = Pedido.objects.select_for_update().get(pk=pedido.pk)
        if not pedido_bloqueado.estoque_reservado:
            return

        for item in pedido_bloqueado.itens:
            Produto.objects.filter(pk=item['produto_id']).update(
                quantidade=F('quantidade') + item['quantidade']
            )

        pedido_bloqueado.estoque_reservado = False
        pedido_bloqueado.save(update_fields=['estoque_reservado'])
        pedido.estoque_reservado = False


def _sincronizar_pagamento(pedido, pagamento):
    if str(pagamento.get('external_reference')) != str(pedido.pk):
        return False
    if pagamento.get('currency_id') != 'BRL':
        return False
    try:
        valor_pago = Decimal(str(pagamento.get('transaction_amount')))
    except (InvalidOperation, TypeError, ValueError):
        return False
    if valor_pago != pedido.total:
        return False

    status = {
        'approved': Pedido.Status.APROVADO,
        'pending': Pedido.Status.PENDENTE,
        'in_process': Pedido.Status.PENDENTE,
        'authorized': Pedido.Status.PENDENTE,
        'rejected': Pedido.Status.RECUSADO,
        'cancelled': Pedido.Status.CANCELADO,
        'refunded': Pedido.Status.REEMBOLSADO,
        'charged_back': Pedido.Status.CONTESTADO,
    }.get(pagamento.get('status'))
    if not status:
        return False

    with transaction.atomic():
        pedido_bloqueado = Pedido.objects.select_for_update().get(pk=pedido.pk)
        pedido_bloqueado.status = status
        pedido_bloqueado.pagamento_id = str(pagamento.get('id', ''))
        pedido_bloqueado.save(update_fields=['status', 'pagamento_id'])
        if status in {Pedido.Status.RECUSADO, Pedido.Status.CANCELADO}:
            _liberar_estoque(pedido_bloqueado)

    pedido.status = status
    pedido.pagamento_id = str(pagamento.get('id', ''))
    return True


def carrinho(request):
    produtos = [
        {
            'id': produto.id,
            'nome': produto.nome,
            'preco': str(produto.preco),
            'quantidade': produto.quantidade,
            'imagem': produto.imagem.url if produto.imagem else '',
        }
        for produto in Produto.objects.order_by('nome')
    ]
    return render(
        request,
        'carrinho/carrinho.html',
        {'produtos_json': produtos},
    )


@login_required(login_url='login')
@require_POST
def iniciar_checkout(request):
    if not settings.MERCADOPAGO_ACCESS_TOKEN:
        messages.error(request, 'O pagamento ainda não está configurado.')
        return redirect('carrinho')

    try:
        carrinho = normalizar_carrinho(request.POST.get('cart', ''))
    except ValueError as erro:
        messages.error(request, str(erro))
        return redirect('carrinho')

    try:
        with transaction.atomic():
            ids_produtos = {item['produto_id'] for item in carrinho}
            produtos = Produto.objects.select_for_update().filter(
                pk__in=ids_produtos
            ).order_by('pk')
            produtos_por_id = {produto.id: produto for produto in produtos}
            if len(produtos_por_id) != len(ids_produtos):
                raise ValueError('Um produto do carrinho não está mais disponível.')

            itens_pedido = []
            subtotal = Decimal('0.00')
            for item in carrinho:
                produto = produtos_por_id[item['produto_id']]
                quantidade = item['quantidade']
                if produto.preco <= 0:
                    raise ValueError(f'O produto {produto.nome} está sem preço.')
                if produto.quantidade < quantidade:
                    raise ValueError(
                        f'Estoque insuficiente para {produto.nome}. '
                        f'Disponível: {produto.quantidade}.'
                    )
                itens_pedido.append({
                    'produto_id': produto.id,
                    'nome': produto.nome,
                    'categoria': produto.categoria,
                    'quantidade': quantidade,
                    'preco_unitario': str(produto.preco),
                })
                subtotal += produto.preco * quantidade

            frete = (
                Decimal('0.00')
                if subtotal >= FRETE_GRATIS_A_PARTIR_DE
                else FRETE_PADRAO
            )
            pedido = Pedido.objects.create(
                itens=itens_pedido,
                subtotal=subtotal,
                frete=frete,
                total=subtotal + frete,
            )

            for item in itens_pedido:
                estoque_atualizado = Produto.objects.filter(
                    pk=item['produto_id'],
                    quantidade__gte=item['quantidade'],
                ).update(
                    quantidade=F('quantidade') - item['quantidade']
                )
                if not estoque_atualizado:
                    raise ValueError(
                        'O estoque mudou. Atualize o carrinho e tente novamente.'
                    )

            pedido.estoque_reservado = True
            pedido.save(update_fields=['estoque_reservado'])
    except ValueError as erro:
        messages.error(request, str(erro))
        return redirect('carrinho')

    try:
        preferencia_id, url_checkout = _criar_preferencia(pedido)
    except ErroMercadoPago:
        _liberar_estoque(pedido)
        pedido.status = Pedido.Status.FALHOU
        pedido.save(update_fields=['status'])
        messages.error(
            request,
            'Não foi possível iniciar o pagamento. Tente novamente em instantes.',
        )
        return redirect('carrinho')

    pedido.preferencia_id = preferencia_id
    pedido.status = Pedido.Status.PENDENTE
    pedido.save(update_fields=['preferencia_id', 'status'])
    return redirect(url_checkout)


def resultado_checkout(request):
    pedido_id = request.GET.get('pedido') or request.GET.get('external_reference')
    try:
        pedido_id = UUID(str(pedido_id))
    except (ValueError, TypeError, AttributeError) as erro:
        raise Http404 from erro
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    pagamento_id = request.GET.get('payment_id') or request.GET.get('collection_id')

    if pagamento_id and pagamento_id.isdigit() and settings.MERCADOPAGO_ACCESS_TOKEN:
        try:
            pagamento = _chamar_api_mercado_pago(
                'GET', f'/v1/payments/{pagamento_id}'
            )
            _sincronizar_pagamento(pedido, pagamento)
        except ErroMercadoPago:
            pass

    return render(request, 'carrinho/resultado.html', {'pedido': pedido})


@csrf_exempt
@require_POST
def webhook_mercado_pago(request):
    try:
        dados = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    dados_pagamento = dados.get('data')
    if not isinstance(dados_pagamento, dict):
        dados_pagamento = {}
    pagamento_id = (
        request.GET.get('data.id')
        or request.GET.get('id')
        or dados_pagamento.get('id')
    )
    if not pagamento_id or not str(pagamento_id).isdigit():
        return HttpResponseBadRequest('Identificador de pagamento inválido.')
    if not _assinatura_webhook_valida(request, pagamento_id):
        return HttpResponse(status=401)
    if not settings.MERCADOPAGO_ACCESS_TOKEN:
        return HttpResponse(status=503)

    try:
        pagamento = _chamar_api_mercado_pago(
            'GET', f'/v1/payments/{pagamento_id}'
        )
    except ErroMercadoPago:
        return HttpResponse(status=502)

    try:
        pedido_id = UUID(str(pagamento.get('external_reference')))
    except (ValueError, TypeError, AttributeError):
        return HttpResponse(status=200)
    pedido = Pedido.objects.filter(pk=pedido_id).first()
    if not pedido:
        return HttpResponse(status=200)
    _sincronizar_pagamento(pedido, pagamento)
    return HttpResponse(status=200)
