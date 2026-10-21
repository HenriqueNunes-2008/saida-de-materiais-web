"""Define os funcionarios usados nos registros de saida de materiais."""

from extensions import db


class Employee(db.Model):
    """Armazena o nome e, quando disponivel, o setor do funcionario."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)
    sector = db.Column(db.String(80))
