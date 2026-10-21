"""Define os projetos associados aos registros de saida de materiais."""

from extensions import db


class Project(db.Model):
    """Armazena os nomes unicos dos projetos."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)
