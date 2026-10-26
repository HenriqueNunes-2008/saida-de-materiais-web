"""Define o cadastro do produto, seus limites e o saldo atual."""

from extensions import db


class Product(db.Model):
    """Representa um produto mantido em uma unidade de estoque."""

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Text, unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    purchase_unit = db.Column(db.String(20), nullable=False)
    stock_unit = db.Column(db.String(20), nullable=False)
    conversion_factor = db.Column(db.Numeric(18, 6), nullable=False, default=1)
    last_unit_price = db.Column(db.Numeric(18, 6))
    stock_quantity = db.Column(db.Numeric(18, 3), nullable=False, default=0)
    average_unit_cost = db.Column(db.Numeric(18, 6), nullable=False, default=0)
    last_purchase_price = db.Column(db.Numeric(18, 6))
    minimum_stock = db.Column(db.Numeric(18, 3), nullable=True)
    reorder_point = db.Column(db.Numeric(18, 3), nullable=True)
    maximum_stock = db.Column(db.Numeric(18, 3), nullable=True)
    stock_pending_review = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
