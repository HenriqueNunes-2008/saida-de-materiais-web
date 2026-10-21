"""Define o usuario autenticavel e seus dados de perfil e permissao."""

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class User(db.Model, UserMixin):
    """Representa uma conta que pode acessar o sistema."""

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

    def set_password(self, password: str) -> None:
        """Armazena somente o hash da senha informada."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Confere a senha digitada contra o hash armazenado."""
        return check_password_hash(self.password_hash, password)
