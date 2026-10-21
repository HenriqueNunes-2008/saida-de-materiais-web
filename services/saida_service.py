"""Executa operacoes ligadas a registros legados de saida de materiais."""

from flask_login import current_user

from extensions import db
from models import Employee, MaterialOutput, Project


def get_nomes():
    """Retorna os nomes de funcionarios para os formularios de saida."""
    return [item.name for item in Employee.query.order_by(Employee.name).all()]


def get_projetos():
    """Retorna os projetos cadastrados para selecao nos formularios."""
    return [item.name for item in Project.query.order_by(Project.name).all()]


def get_report_suggestions():
    """Monta valores distintos usados nas sugestoes dos filtros de relatorio."""
    suggestion_map = {"projects": [], "materials": [], "employees": []}
    try:
        projects = (
            db.session.query(MaterialOutput.project_name)
            .filter(MaterialOutput.project_name.isnot(None))
            .distinct()
            .order_by(MaterialOutput.project_name)
            .all()
        )
        suggestion_map["projects"] = [item[0] for item in projects if item[0]]

        materials = (
            db.session.query(MaterialOutput.material)
            .filter(MaterialOutput.material.isnot(None))
            .distinct()
            .order_by(MaterialOutput.material)
            .all()
        )
        suggestion_map["materials"] = [item[0] for item in materials if item[0]]

        employees = (
            db.session.query(MaterialOutput.employee_name)
            .filter(MaterialOutput.employee_name.isnot(None))
            .distinct()
            .order_by(MaterialOutput.employee_name)
            .all()
        )
        suggestion_map["employees"] = [item[0] for item in employees if item[0]]
    except Exception:
        db.session.rollback()
        raise
    return suggestion_map


def registrar_saida(dados):
    """Grava uma saida antiga que nao possui vinculo ao estoque integrado."""
    recorded_by = current_user.id if current_user.is_authenticated else None
    material_output = MaterialOutput(
        employee_name=dados[1],
        project_name=dados[2],
        material=dados[3],
        quantity=int(dados[4]),
        recorded_by=recorded_by,
    )
    db.session.add(material_output)
    db.session.commit()
