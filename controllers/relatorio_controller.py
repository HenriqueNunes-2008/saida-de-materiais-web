from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User, Employee, Project, MaterialOutput
from services.legacy_service import get_nomes, get_projetos, get_report_suggestions, registrar_saida, gerar_excel
import secrets
from services.relatorio_financeiro import valores_historicos

@login_required
def report():
    if not (current_user.sector in ['Almoxarifado', 'Compras']):
        flash('Acesso negado. Apenas Almoxarifado e Compras podem visualizar relatórios.', 'error')
        return redirect(url_for('index'))

    period = request.args.get('period', 'all')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    project_filter = request.args.get('project', '').strip()
    material_filter = request.args.get('material', '').strip()
    employee_filter = request.args.get('employee', '').strip()

    query = MaterialOutput.query

    if project_filter:
        query = query.filter(MaterialOutput.project_name.contains(project_filter))
    if material_filter:
        query = query.filter(MaterialOutput.material.contains(material_filter))
    if employee_filter:
        query = query.filter(MaterialOutput.employee_name.contains(employee_filter))

    now = datetime.now()
    if period == '7d':
        query = query.filter(MaterialOutput.created_at >= now - timedelta(days=7))
    elif period == '30d':
        query = query.filter(MaterialOutput.created_at >= now - timedelta(days=30))
    elif period == 'custom':
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(MaterialOutput.created_at >= start_dt)
            except ValueError:
                pass
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(MaterialOutput.created_at < end_dt)
            except ValueError:
                pass

    material_outputs = query.order_by(MaterialOutput.created_at.desc()).all()
    suggestions = get_report_suggestions()

    return render_template(
        'report.html',
        material_outputs=material_outputs,
        valores=valores_historicos(material_outputs),
        suggestions=suggestions,
        can_edit=current_user.sector == 'Almoxarifado',
        title='Relatório',
        filters={
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'project': project_filter,
            'material': material_filter,
            'employee': employee_filter,
        }
    )


def register_routes(app):
    app.add_url_rule('/report', endpoint="report", view_func=report)
