"""Movimentações com unidade única e quantidades decimais para KG/M."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timezone
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import Product, StockMovement, MaterialOutput

SIX = Decimal('0.000001')
THREE = Decimal('0.001')
MAX_QTY = Decimal('999999999999999.999')
MAX_MOVEMENT_TOTAL = Decimal('99999999999999.999999')
UNITS = ('UN', 'CX', 'KG', 'M', 'PC', 'MT', 'PT', 'BR', 'CH', 'PA', 'LT', 'JG', 'CJ', 'RL', 'CT')
# Na planilha, UM é uma anotação equivalente a UN; o código salvo no sistema é UN.
IMPORT_UNIT_MAP = {'UM': 'UN'}
FRACTIONAL_UNITS = ('KG', 'M', 'MT', 'LT')

def search_active_products(term, limit=10):
    """Busca produtos ativos por código ou descrição, sem diferenciar maiúsculas."""
    term = str(term or '').strip()
    if not term:
        return []
    pattern = f'%{term}%'
    return db.session.execute(
        select(Product)
        .where(Product.active.is_(True), or_(
            Product.code.ilike(pattern), Product.description.ilike(pattern)
        ))
        .order_by(Product.code)
        .limit(min(max(int(limit), 1), 20))
    ).scalars().all()

class StockValidationError(ValueError):
    pass

def movement_total(quantity, price):
    try:
        total = (quantity * price).quantize(SIX, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise StockValidationError('O valor total excede o limite financeiro suportado pelo banco.') from exc
    if total > MAX_MOVEMENT_TOTAL:
        raise StockValidationError('O valor total excede o limite financeiro suportado pelo banco.')
    return total

def clean_field(raw, label, maximum):
    value = str(raw or '').strip()
    if not value or len(value) > maximum:
        raise StockValidationError(f'{label}: preencha entre 1 e {maximum} caracteres.')
    return value

def valid_unit(raw):
    value = clean_field(raw, 'Unidade', 20).upper()
    value = IMPORT_UNIT_MAP.get(value, value)
    if value not in UNITS:
        raise StockValidationError('Unidade inválida. Utilize uma unidade disponível no cadastro.')
    return value

def valid_quantity(raw, unit):
    try:
        value = Decimal(str(raw).strip().replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError):
        raise StockValidationError('Informe uma quantidade numérica válida.')
    if not value.is_finite() or value <= 0 or value > MAX_QTY or value.as_tuple().exponent < -3:
        raise StockValidationError('A quantidade deve ser positiva e ter no máximo três casas decimais.')
    if unit not in FRACTIONAL_UNITS and value != value.to_integral_value():
        raise StockValidationError(f'A unidade {unit} exige quantidade inteira.')
    return value

def valid_stock_balance(raw, unit):
    # A edicao aceita zero para correcao, mas respeita escala e regra da unidade.
    try:
        value = Decimal(str(raw).strip().replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError):
        raise StockValidationError('Informe um saldo numérico válido.')
    if not value.is_finite() or value < 0 or value > MAX_QTY or value.as_tuple().exponent < -3:
        raise StockValidationError('O saldo deve ser não negativo e ter no máximo três casas decimais.')
    if unit not in FRACTIONAL_UNITS and value != value.to_integral_value():
        raise StockValidationError(f'A unidade {unit} exige saldo inteiro.')
    return value

def valid_price(raw):
    try:
        value = Decimal(str(raw).strip().replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError):
        raise StockValidationError('Informe um preço válido.')
    if not value.is_finite() or value < 0 or value.as_tuple().exponent < -6 or value >= Decimal('1000000000000'):
        raise StockValidationError('Preço inválido: utilize até seis casas decimais.')
    return value

def add_entry(product, kind, qty, price, actor_id, notes):
    before = Decimal(product.stock_quantity or 0)
    after = before + qty
    if after > MAX_QTY:
        raise StockValidationError('Estoque excederia o limite permitido.')
    avg = Decimal(product.average_unit_cost or 0)
    total = movement_total(qty, price)
    new_avg = ((before * avg + total) / after).quantize(SIX, rounding=ROUND_HALF_UP)
    db.session.add(StockMovement(product_id=product.id, movement_type=kind,
        quantity=qty, original_quantity=qty, original_unit=product.stock_unit,
        conversion_factor=1, original_unit_price=price, purchase_unit_price=price,
        applied_unit_price=price, applied_total_value=total, unit_cost=price,
        total_cost=total, stock_before=before, stock_after=after,
        average_cost_before=avg, average_cost_after=new_avg,
        recorded_by=actor_id, notes=notes))
    product.stock_quantity=after
    product.average_unit_cost=new_avg
    product.last_unit_price=price
    product.last_purchase_price=price
    product.updated_at=datetime.now(timezone.utc)

def create_product(code, description, unit, quantity, price, actor_id, minimum_stock=None, reorder_point=None):
    code=clean_field(code,'Código',100)
    description=clean_field(description,'Descrição',500)
    unit=valid_unit(unit)
    qty=valid_quantity(quantity,unit)
    price=valid_price(price)
    minimum_stock=valid_stock_limit(minimum_stock, 'Estoque mínimo', unit)
    reorder_point=valid_stock_limit(reorder_point, 'Gatilho de reposição', unit)
    if minimum_stock is not None and reorder_point is not None and reorder_point < minimum_stock:
        raise StockValidationError('O gatilho deve ser maior ou igual ao estoque mínimo.')
    if db.session.execute(select(Product.id).where(Product.code==code)).first():
        raise StockValidationError('Código já cadastrado.')
    try:
        product=Product(code=code,description=description,unit=unit,purchase_unit=unit,
            stock_unit=unit,conversion_factor=1,stock_quantity=Decimal('0'),average_unit_cost=Decimal('0'),
            minimum_stock=minimum_stock,reorder_point=reorder_point)
        db.session.add(product);db.session.flush()
        add_entry(product,'SALDO_INICIAL',qty,price,actor_id,'Cadastro inicial')
        db.session.commit()
        return product
    except IntegrityError as exc:
        db.session.rollback()
        raise StockValidationError('Código já cadastrado ou dados inválidos.') from exc
    except Exception:
        db.session.rollback();raise

def register_simple_entry(product_id, quantity, actor_id):
    try:
        product=db.session.execute(select(Product).where(Product.id==product_id).with_for_update()).scalar_one_or_none()
        if not product or not product.active:raise StockValidationError('Produto não encontrado ou inativo.')
        qty=valid_quantity(quantity,product.stock_unit)
        if product.last_unit_price is None:raise StockValidationError('Defina o preço no cadastro.')
        add_entry(product,'ENTRADA',qty,Decimal(product.last_unit_price),actor_id,'Reposição simplificada')
        db.session.commit();return product
    except Exception:
        db.session.rollback();raise

def edit_product(product_id, description, quantity, price, minimum_stock, reorder_point, actor_id, confirm_stock=False):
    description=clean_field(description,'Descricao',500)
    price=valid_price(price)
    try:
        product=db.session.execute(select(Product).where(Product.id==product_id).with_for_update()).scalar_one_or_none()
        if not product or not product.active:raise StockValidationError('Produto nao encontrado ou inativo.')
        if product.stock_pending_review and not confirm_stock:
            raise StockValidationError('Confirme explicitamente o saldo físico antes de salvar este produto.')
        quantity=valid_stock_balance(quantity, product.stock_unit)
        minimum_stock=valid_stock_limit(minimum_stock, 'Estoque minimo', product.stock_unit)
        reorder_point=valid_stock_limit(reorder_point, 'Gatilho de reposicao', product.stock_unit)
        if minimum_stock is not None and reorder_point is not None and reorder_point < minimum_stock:
            raise StockValidationError('O gatilho deve ser maior ou igual ao estoque minimo.')

        before=Decimal(product.stock_quantity or 0)
        average=Decimal(product.average_unit_cost or 0)
        if quantity != before:
            delta=abs(quantity-before)
            total=movement_total(delta, average)
            # A diferenca positiva e acompanhada por antes/depois para auditar aumentos e reducoes.
            db.session.add(StockMovement(product_id=product.id, movement_type='AJUSTE_SALDO',
                quantity=delta, original_quantity=delta, original_unit=product.stock_unit,
                conversion_factor=1, applied_unit_price=average, applied_total_value=total,
                unit_cost=average, total_cost=total, stock_before=before, stock_after=quantity,
                average_cost_before=average, average_cost_after=average, recorded_by=actor_id,
                notes=f'Ajuste manual de saldo: {before} para {quantity} {product.stock_unit}.'))
            product.stock_quantity=quantity

        if confirm_stock:
            product.stock_pending_review=False
        product.description=description
        product.last_unit_price=price;product.last_purchase_price=price
        product.minimum_stock=minimum_stock;product.reorder_point=reorder_point
        product.updated_at=datetime.now(timezone.utc)
        db.session.commit()
    except Exception:
        db.session.rollback();raise

def valid_stock_limit(raw, label, unit=None):
    if raw is None or not str(raw).strip():
        return None
    try:
        value = Decimal(str(raw).strip().replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError):
        raise StockValidationError(f'{label} deve ser numérico.')
    if not value.is_finite() or value < 0 or value > MAX_QTY or value.as_tuple().exponent < -3:
        raise StockValidationError(f'{label} deve ser não negativo e ter até três casas decimais.')
    if unit and unit not in FRACTIONAL_UNITS and value != value.to_integral_value():
        raise StockValidationError(f'{label} deve ser inteiro para a unidade {unit}.')
    return value

def reorder_status(product):
    # Pendencia fisica prevalece sobre limites; depois sao aplicados minimo e gatilho.
    if getattr(product, 'stock_pending_review', False):
        return 'Saldo pendente de conferência'
    minimum, trigger = product.minimum_stock, product.reorder_point
    if minimum is None and trigger is None:
        return 'Sem gatilho'
    qty = Decimal(product.stock_quantity or 0)
    if minimum is not None and qty <= Decimal(minimum):
        return 'Estoque crítico'
    if trigger is not None and qty <= Decimal(trigger):
        return 'Reposição necessária'
    return 'Normal'

def get_returnable(output_id):
    output=db.session.get(MaterialOutput,output_id)
    if not output or output.product_id is None:raise StockValidationError('Saída sem baixa automática.')
    original=db.session.execute(select(StockMovement).where(StockMovement.material_output_id==output.id,StockMovement.movement_type=='SAIDA')).scalar_one_or_none()
    if not original:raise StockValidationError('Movimentação original não encontrada.')
    returned=db.session.execute(select(func.coalesce(func.sum(StockMovement.quantity),0)).where(StockMovement.original_output_id==output.id,StockMovement.movement_type=='ESTORNO_SAIDA')).scalar_one()
    return output,original,Decimal(original.quantity)-Decimal(returned)

def register_return(output_id,quantity,actor_id,reason):
    reason=clean_field(reason,'Motivo da devolução',500)
    try:
        output=db.session.get(MaterialOutput,output_id)
        if not output or output.product_id is None:raise StockValidationError('Saída sem baixa automática.')
        product=db.session.execute(select(Product).where(Product.id==output.product_id).with_for_update()).scalar_one_or_none()
        if not product:raise StockValidationError('Produto não encontrado.')
        qty=valid_quantity(quantity,product.stock_unit)
        original=db.session.execute(select(StockMovement).where(StockMovement.material_output_id==output.id,StockMovement.movement_type=='SAIDA')).scalar_one_or_none()
        if not original:raise StockValidationError('Movimentação original não encontrada.')
        already=Decimal(db.session.execute(select(func.coalesce(func.sum(StockMovement.quantity),0)).where(StockMovement.original_output_id==output.id,StockMovement.movement_type=='ESTORNO_SAIDA')).scalar_one())
        remaining=Decimal(original.quantity)-already
        if qty>remaining:raise StockValidationError(f'Devolução excede a saída. Restam {remaining} {product.stock_unit}.')
        before=Decimal(product.stock_quantity);after=before+qty
        if after>MAX_QTY:raise StockValidationError('Estoque excederia o limite permitido.')
        price=Decimal(original.applied_unit_price if original.applied_unit_price is not None else original.unit_cost)
        total=movement_total(qty, price)
        avg=Decimal(product.average_unit_cost or 0)
        db.session.add(StockMovement(product_id=product.id,movement_type='ESTORNO_SAIDA',quantity=qty,
            original_quantity=qty,original_unit=product.stock_unit,conversion_factor=1,
            applied_unit_price=price,applied_total_value=total,unit_cost=price,total_cost=total,
            stock_before=before,stock_after=after,average_cost_before=avg,average_cost_after=avg,
            original_output_id=output.id,recorded_by=actor_id,notes=reason))
        product.stock_quantity=after;product.updated_at=datetime.now(timezone.utc)
        db.session.commit()
    except Exception:
        db.session.rollback();raise

def register_output(product_id,employee_name,project_name,quantity,actor_id):
    employee_name=clean_field(employee_name,'Funcionário',500)
    project_name=clean_field(project_name,'Projeto',500)
    try:
        product=db.session.execute(select(Product).where(Product.id==product_id).with_for_update()).scalar_one_or_none()
        if not product or not product.active:raise StockValidationError('Produto não encontrado ou inativo.')
        qty=valid_quantity(quantity,product.stock_unit)
        before=Decimal(product.stock_quantity)
        if qty>before:raise StockValidationError(f'Saldo insuficiente: {before} {product.stock_unit}.')
        if product.last_unit_price is None:raise StockValidationError('Produto sem preço cadastrado.')
        price=Decimal(product.last_unit_price);total=movement_total(qty, price)
        avg=Decimal(product.average_unit_cost or 0)
        output=MaterialOutput(employee_name=employee_name,project_name=project_name,
            material=product.code,quantity=qty,recorded_by=actor_id,product_id=product.id)
        db.session.add(output);db.session.flush()
        db.session.add(StockMovement(product_id=product.id,movement_type='SAIDA',quantity=qty,
            original_quantity=qty,original_unit=product.stock_unit,conversion_factor=1,
            applied_unit_price=price,applied_total_value=total,unit_cost=price,total_cost=total,
            stock_before=before,stock_after=before-qty,average_cost_before=avg,average_cost_after=avg,
            material_output_id=output.id,recorded_by=actor_id,
            notes=f'Saída para {project_name}; funcionário {employee_name}'))
        product.stock_quantity=before-qty;product.updated_at=datetime.now(timezone.utc)
        db.session.commit();return output
    except Exception:
        db.session.rollback();raise
