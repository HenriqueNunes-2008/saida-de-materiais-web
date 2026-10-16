"""Valores históricos de saídas e estornos; não usa preço atual."""
from decimal import Decimal
from sqlalchemy import select
from extensions import db
from models import StockMovement, Product

def valores_historicos(outputs):
    ids=[item.id for item in outputs]
    if not ids:return {}
    movements=db.session.execute(select(StockMovement).where(
        ((StockMovement.material_output_id.in_(ids)) & (StockMovement.movement_type=='SAIDA')) |
        ((StockMovement.original_output_id.in_(ids)) & (StockMovement.movement_type=='ESTORNO_SAIDA'))
    )).scalars().all()
    products={p.id:p.stock_unit for p in db.session.execute(select(Product).where(Product.id.in_([m.product_id for m in movements]))).scalars().all()}
    result={}
    for m in movements:
        if m.movement_type=='SAIDA':
            price=Decimal(m.applied_unit_price if m.applied_unit_price is not None else m.unit_cost)
            total=Decimal(m.applied_total_value if m.applied_total_value is not None else m.total_cost)
            result[m.material_output_id]={'unit_price':price,'total_value':total,
                'returned_qty':Decimal(0),'returned_value':Decimal(0),'unit':m.original_unit or products.get(m.product_id,'—'), 'returns':[]}
    for m in movements:
        if m.movement_type=='ESTORNO_SAIDA' and m.original_output_id in result:
            d=result[m.original_output_id]
            d['returned_qty']+=Decimal(m.quantity)
            d['returned_value']+=Decimal(m.applied_total_value if m.applied_total_value is not None else m.total_cost)
            d['returns'].append({'date':m.created_at,'quantity':m.quantity,'reason':m.notes or '—'})
    for o in outputs:
        if o.id in result:
            d=result[o.id]
            d['net_qty']=Decimal(o.quantity)-d['returned_qty']
            d['net_value']=d['total_value']-d['returned_value']
            d['status']='Estorno total' if d['returned_qty']==Decimal(o.quantity) else ('Estorno parcial' if d['returned_qty']>0 else 'Sem estorno')
    return result
