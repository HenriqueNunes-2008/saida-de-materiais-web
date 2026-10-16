from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    sector = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    active = db.Column(db.Boolean, default=False)
    approved = db.Column(db.Boolean, default=False)
    reset_required = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)
    sector = db.Column(db.String(80))


class MaterialOutput(db.Model):
    __tablename__ = "material_output"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.TIMESTAMP(timezone=True), server_default=db.func.now(), nullable=False)
    employee_name = db.Column(db.Text, nullable=False)
    project_name = db.Column(db.Text)
    material = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Numeric(18, 3), nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)


class Product(db.Model):
    __tablename__ = 'products'
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
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
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
    material_output_id = db.Column(db.Integer, db.ForeignKey('material_output.id'), unique=True)
    original_output_id = db.Column(db.Integer, db.ForeignKey('material_output.id'), nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
