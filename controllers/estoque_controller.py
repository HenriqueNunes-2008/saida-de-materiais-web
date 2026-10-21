"""Rotas do controle de estoque, com acesso por perfil e alertas de reposicao."""
from functools import wraps
import secrets
from decimal import Decimal
from flask import render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user
from sqlalchemy import select, func, case
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from models import Product, StockMovement
from services.estoque_service import create_product, register_simple_entry, edit_product, get_returnable, register_return, StockValidationError, UNITS, reorder_status

def estoque_read_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.sector not in ('Almoxarifado', 'Compras'):
            abort(403)
        return fn(*args, **kwargs)
    return wrapped

def almox_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.sector != 'Almoxarifado':
            abort(403)
        return fn(*args, **kwargs)
    return wrapped

def csrf_token():
    if 'estoque_csrf' not in session:
        session['estoque_csrf'] = secrets.token_urlsafe(32)
    return session['estoque_csrf']

def verify_csrf():
    if not secrets.compare_digest(str(request.form.get('csrf_token', '')), csrf_token()):
        abort(400, description='Formulário expirado ou inválido. Atualize a página.')

def obter_notificacoes_estoque():
    """Agrupa cada produto ativo em seu alerta confirmado mais urgente."""
    produtos = db.session.execute(
        select(Product).where(Product.active.is_(True)).order_by(Product.code)
    ).scalars().all()
    grupos = [
        {'titulo': 'Produtos sem saldo', 'produtos': []},
        {'titulo': 'Produtos no estoque mínimo', 'produtos': []},
        {'titulo': 'Produtos no gatilho de reposição', 'produtos': []},
    ]

    for produto in produtos:
        # Saldo sem quantidade confirmada nao gera falso alerta de estoque zero.
        if produto.stock_pending_review:
            continue
        saldo = Decimal(produto.stock_quantity or 0)
        minimo = Decimal(produto.minimum_stock) if produto.minimum_stock is not None else None
        gatilho = Decimal(produto.reorder_point) if produto.reorder_point is not None else None

        # Cada produto aparece uma vez; saldo zero tem prioridade sobre mínimo e gatilho.
        if saldo <= 0:
            grupos[0]['produtos'].append(produto)
        elif minimo is not None and saldo <= minimo:
            grupos[1]['produtos'].append(produto)
        elif gatilho is not None and saldo <= gatilho:
            grupos[2]['produtos'].append(produto)

    grupos_com_itens = [grupo for grupo in grupos if grupo['produtos']]
    total = sum(len(grupo['produtos']) for grupo in grupos_com_itens)
    return grupos_com_itens, total


def estoque():
    # Filtros afetam a lista; o sino sempre resume os alertas do estoque ativo inteiro.
    term = request.args.get('q', '').strip()
    unit = request.args.get('unit', '').strip().upper()
    status = request.args.get('status', 'all').strip()
    if unit not in ('', *UNITS):
        unit = ''
    if status not in ('all', 'active', 'inactive', 'positive', 'zero'):
        status = 'all'

    query = select(Product).order_by(Product.code)
    if term:
        query = query.where(Product.code.ilike(f'%{term}%') | Product.description.ilike(f'%{term}%'))
    if unit:
        query = query.where(Product.stock_unit == unit)
    if status == 'active':
        query = query.where(Product.active.is_(True))
    elif status == 'inactive':
        query = query.where(Product.active.is_(False))
    elif status == 'positive':
        query = query.where(Product.stock_quantity > 0)
    elif status == 'zero':
        query = query.where(Product.stock_quantity == 0)
    # Os indicadores usam exatamente os mesmos filtros da tabela, mas sem
    # o limite de 200 registros aplicado apenas à visualização.
    filtered = query.order_by(None).subquery()
    zero = Decimal('0')
    summary = db.session.execute(
        select(
            func.count(filtered.c.id).label('total_products'),
            func.coalesce(func.sum(
                filtered.c.stock_quantity * filtered.c.average_unit_cost
            ), 0).label('total_value'),
            func.coalesce(func.sum(case(
                (filtered.c.stock_quantity == 0, 1), else_=0
            )), 0).label('zero_products'),
            func.coalesce(func.sum(filtered.c.stock_quantity), 0).label('total_quantity'),
        )
    ).one()
    status_products = db.session.execute(query).scalars().all()
    status_counts = {'Normal': 0, 'Reposição necessária': 0, 'Estoque crítico': 0, 'Sem gatilho': 0, 'Saldo pendente de conferência': 0}
    for item in status_products:
        label = reorder_status(item)
        status_counts[label] = status_counts.get(label, 0) + 1
    products = status_products[:200]
    statuses = {p.id: reorder_status(p) for p in products}
    # Só somamos quantidades quando todas compartilham a mesma unidade.
    # Caso contrário, somar metros, caixas e quilos não tem significado.
    total_quantity = summary.total_quantity if unit else None
    alert_groups, alert_count = obter_notificacoes_estoque()
    return render_template(
        'estoque.html', products=products, search=term,
        selected_unit=unit, selected_status=status,
        total_products=summary.total_products,
        total_value=summary.total_value or zero,
        zero_products=summary.zero_products,
        total_quantity=total_quantity, reorder_statuses=statuses, status_counts=status_counts,
        alert_groups=alert_groups, alert_count=alert_count,
        has_filters=bool(term or unit or status != 'all'),
        displayed_count=len(products),
        title='Controle de Estoque', csrf_token=csrf_token()
    )

def cadastro_produto():
    if request.method == 'POST':
        verify_csrf()
        try:
            create_product(request.form.get('code'), request.form.get('description'),
                           request.form.get('unit'), request.form.get('quantity'),
                           request.form.get('price'), current_user.id,
                           request.form.get('minimum_stock'), request.form.get('reorder_point'))
            flash('Produto cadastrado e saldo inicial registrado com sucesso.', 'success')
            return redirect(url_for('estoque'))
        except StockValidationError as exc:
            db.session.rollback()
            flash(str(exc), 'error')
        except SQLAlchemyError:
            db.session.rollback()
            flash('Falha ao salvar o produto. Nenhuma alteração foi confirmada.', 'error')
    return render_template('estoque_cadastro.html', title='Cadastrar Produto', csrf_token=csrf_token())

def detalhe_produto(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        abort(404)
    movements = db.session.execute(select(StockMovement).where(StockMovement.product_id == product_id)
                                   .order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).limit(100)).scalars().all()
    return render_template('estoque_detalhe.html', product=product, movements=movements,
                           title='Detalhes do Produto', csrf_token=csrf_token())

def nova_entrada_produto(product_id):
    product = db.session.get(Product, product_id)
    if product is None or not product.active:
        abort(404)
    return render_template('estoque_nova_entrada.html', product=product,
                           title='Nova Entrada', csrf_token=csrf_token())

def formulario_editar_produto(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        abort(404)
    return render_template('estoque_editar.html', product=product,
                           title='Editar Produto', csrf_token=csrf_token())

def entrada_produto(product_id):
    verify_csrf()
    try:
        register_simple_entry(product_id, request.form.get('quantity'), current_user.id)
        flash('Entrada registrada com a unidade e o preço cadastrados.', 'success')
    except StockValidationError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
    except SQLAlchemyError:
        db.session.rollback()
        flash('Falha ao registrar entrada. Nenhuma alteração foi confirmada.', 'error')
    return redirect(url_for('nova_entrada_produto', product_id=product_id))

def editar_produto(product_id):
    verify_csrf()
    try:
        edit_product(product_id, request.form.get('description'), request.form.get('quantity'),
                     request.form.get('price'), request.form.get('minimum_stock'),
                     request.form.get('reorder_point'), current_user.id,
                     request.form.get('confirm_stock') == 'yes')
        flash('Produto atualizado. Se o saldo mudou, o ajuste ficou registrado no histórico.', 'success')
    except StockValidationError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
    except SQLAlchemyError:
        db.session.rollback()
        flash('Não foi possível atualizar o produto.', 'error')
    return redirect(url_for('formulario_editar_produto', product_id=product_id))

def estornar_saida(output_id):
    try:
        output, original, remaining = get_returnable(output_id)
    except StockValidationError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('report'))
    if request.method == 'POST':
        verify_csrf()
        try:
            register_return(output_id, request.form.get('quantity'), current_user.id,
                            request.form.get('reason'))
            flash('Devolução registrada e estoque atualizado com sucesso.', 'success')
            return redirect(url_for('report'))
        except StockValidationError as exc:
            db.session.rollback()
            flash(str(exc), 'error')
        except SQLAlchemyError:
            db.session.rollback()
            flash('Não foi possível registrar a devolução.', 'error')
        output, original, remaining = get_returnable(output_id)
    return render_template('estoque_estorno.html', output=output, original=original,
                           remaining=remaining, title='Estorno de saída', csrf_token=csrf_token())

def register_routes(app):
    app.add_url_rule('/estoque/saidas/<int:output_id>/estornar', methods=['GET', 'POST'], endpoint='estornar_saida', view_func=almox_required(estornar_saida))
    app.add_url_rule('/estoque', endpoint='estoque', view_func=estoque_read_required(estoque))
    app.add_url_rule('/estoque/cadastrar', methods=['GET', 'POST'], endpoint='cadastro_produto', view_func=almox_required(cadastro_produto))
    app.add_url_rule('/estoque/<int:product_id>', endpoint='detalhe_produto', view_func=estoque_read_required(detalhe_produto))
    app.add_url_rule('/estoque/<int:product_id>/nova-entrada', endpoint='nova_entrada_produto', view_func=almox_required(nova_entrada_produto))
    app.add_url_rule('/estoque/<int:product_id>/editar', endpoint='formulario_editar_produto', view_func=almox_required(formulario_editar_produto))
    app.add_url_rule('/estoque/<int:product_id>/entrada', methods=['POST'], endpoint='entrada_produto', view_func=almox_required(entrada_produto))
    app.add_url_rule('/estoque/<int:product_id>/editar', methods=['POST'], endpoint='editar_produto', view_func=almox_required(editar_produto))
