from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User, Employee, Project, MaterialOutput
from services.legacy_service import get_nomes, get_projetos, get_report_suggestions, registrar_saida, gerar_excel
import secrets
from controllers.estoque_controller import almox_required, csrf_token, verify_csrf

@almox_required
def add_nome():
    verify_csrf()
    novo_nome = request.form.get('novo_nome', '').strip()
    if not novo_nome:
        flash('Nome não pode ser vazio.', 'error')
        return redirect(url_for('index'))
    if Employee.query.filter_by(name=novo_nome).first():
        flash('Esse nome já existe.', 'error')
    else:
        db.session.add(Employee(name=novo_nome))
        try:
            db.session.commit()
            flash('Nome adicionado com sucesso!', 'success')
        except SQLAlchemyError:
            db.session.rollback()
            flash('Erro ao cadastrar nome.', 'error')
    return redirect(url_for('index'))


@almox_required
def add_projeto():
    verify_csrf()
    novo_projeto = request.form.get('novo_projeto', '').strip()
    if not novo_projeto:
        flash('Projeto não pode ser vazio.', 'error')
        return redirect(url_for('index'))
    if Project.query.filter_by(name=novo_projeto).first():
        flash('Esse projeto já existe.', 'error')
    else:
        db.session.add(Project(name=novo_projeto))
        try:
            db.session.commit()
            flash('Projeto adicionado com sucesso!', 'success')
        except SQLAlchemyError:
            db.session.rollback()
            flash('Erro ao cadastrar projeto.', 'error')
    return redirect(url_for('index'))


@almox_required
def delete_nome(nome):
    verify_csrf()
    obj = Employee.query.filter_by(name=nome).first()
    if obj is None:
        flash('Registro não encontrado.', 'error')
    else:
        try:
            db.session.delete(obj)
            db.session.commit()
            flash('Registro removido.', 'success')
        except SQLAlchemyError:
            db.session.rollback()
            flash('Erro ao remover registro.', 'error')
    return redirect(url_for('view_lists'))


@almox_required
def delete_projeto(projeto):
    verify_csrf()
    obj = Project.query.filter_by(name=projeto).first()
    if obj is None:
        flash('Registro não encontrado.', 'error')
    else:
        try:
            db.session.delete(obj)
            db.session.commit()
            flash('Registro removido.', 'success')
        except SQLAlchemyError:
            db.session.rollback()
            flash('Erro ao remover registro.', 'error')
    return redirect(url_for('view_lists'))


@almox_required
def view_lists():
    return render_template('view_lists.html', nomes=get_nomes(), projetos=get_projetos(), csrf_token=csrf_token())


def register_routes(app):
    app.add_url_rule('/add_nome', methods=['POST'], endpoint="add_nome", view_func=add_nome)
    app.add_url_rule('/add_projeto', methods=['POST'], endpoint="add_projeto", view_func=add_projeto)
    app.add_url_rule('/delete_nome/<nome>', methods=['POST'], endpoint="delete_nome", view_func=delete_nome)
    app.add_url_rule('/delete_projeto/<projeto>', methods=['POST'], endpoint="delete_projeto", view_func=delete_projeto)
    app.add_url_rule('/view_lists', endpoint="view_lists", view_func=view_lists)
