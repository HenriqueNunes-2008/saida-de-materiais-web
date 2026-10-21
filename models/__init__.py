"""Centraliza os imports publicos dos modelos ORM do sistema."""

# Mantem compatibilidade com `from models import Product` usado nos controllers
# e services, enquanto cada classe fica definida no modulo correspondente.
from .funcionario import Employee
from .movimentacao import StockMovement
from .produto import Product
from .projeto import Project
from .saida import MaterialOutput
from .usuario import User

__all__ = [
    "Employee",
    "MaterialOutput",
    "Product",
    "Project",
    "StockMovement",
    "User",
]
