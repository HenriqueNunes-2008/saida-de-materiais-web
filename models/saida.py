"""Define a saida registrada e sua ligacao opcional ao cadastro de produtos."""

from extensions import db


class MaterialOutput(db.Model):
    """Mantem o registro da saida e a referencia ao usuario que a lancou."""

    __tablename__ = "material_output"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(
        db.TIMESTAMP(timezone=True), server_default=db.func.now(), nullable=False
    )
    employee_name = db.Column(db.Text, nullable=False)
    project_name = db.Column(db.Text)
    material = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Numeric(18, 3), nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
