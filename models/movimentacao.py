"""Define os movimentos de estoque e o historico de custo e saldo."""

from extensions import db


class StockMovement(db.Model):
    """Registra uma entrada, saida, estorno ou ajuste de saldo."""

    __tablename__ = "stock_movements"

    id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    movement_type = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Numeric(18, 3), nullable=False)
    original_quantity = db.Column(db.Numeric(18, 6))
    original_unit = db.Column(db.String(20))
    conversion_factor = db.Column(db.Numeric(18, 6))
    original_unit_price = db.Column(db.Numeric(18, 6))
    applied_unit_price = db.Column(db.Numeric(18, 6))
    applied_total_value = db.Column(db.Numeric(20, 6))
    purchase_unit_price = db.Column(db.Numeric(18, 6))
    unit_cost = db.Column(db.Numeric(18, 6), nullable=False)
    total_cost = db.Column(db.Numeric(20, 6), nullable=False)
    stock_before = db.Column(db.Numeric(18, 3), nullable=False)
    stock_after = db.Column(db.Numeric(18, 3), nullable=False)
    average_cost_before = db.Column(db.Numeric(18, 6), nullable=False)
    average_cost_after = db.Column(db.Numeric(18, 6), nullable=False)
    material_output_id = db.Column(
        db.Integer, db.ForeignKey("material_output.id"), unique=True
    )
    original_output_id = db.Column(
        db.Integer, db.ForeignKey("material_output.id"), nullable=True
    )
    recorded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
