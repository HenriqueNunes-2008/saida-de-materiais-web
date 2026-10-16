from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User, Employee, Project, MaterialOutput
from services.legacy_service import get_nomes, get_projetos, get_report_suggestions, registrar_saida, gerar_excel
import secrets
from controllers.estoque_controller import verify_csrf

def register():
    # existing register handler (unchanged)

    if request.method == 'POST':
        verify_csrf()
        name = request.form.get('name', '').strip()
        sector = request.form.get('sector', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not all([name, sector, email, password]):
            flash('Preencha todos os campos do cadastro.', 'error')
            return redirect(url_for('index'))
        if sector not in ('Almoxarifado', 'Compras'):
            flash('Setor inválido para cadastro.', 'error')
            return redirect(url_for('index'))

        if User.query.filter_by(email=email).first():
            # Keep the response indistinguishable to avoid confirming registered addresses.
            flash('Se os dados forem válidos, o cadastro seguirá para aprovação do TI.', 'success')
            return redirect(url_for('index'))

        user = User(name=name, sector=sector, email=email)
        user.set_password(password)
        # Novo cadastro precisa de aprovação do TI
        user.approved = False
        user.active = False
        db.session.add(user)
        db.session.commit()

        flash('Cadastro realizado. Aguarde a aprovação do TI para ativação do acesso.', 'success')
        return redirect(url_for('index'))

    return redirect(url_for('index'))


def login():
    if request.method == 'POST':
        verify_csrf()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user or not user.approved or not user.active or not user.check_password(password):
            flash('Não foi possível entrar. Verifique as credenciais ou a liberação do acesso.', 'error')
            return redirect(url_for('index'))

        login_user(user)
        flash('Login realizado com sucesso.', 'success')
        # Route TI users to admin panel, Compras to reports, others to index
        if user.sector == 'TI' or user.is_admin:
            return redirect(url_for('admin_panel'))
        if user.sector == 'Compras':
            return redirect(url_for('report'))
        return redirect(url_for('index'))

    return redirect(url_for('index'))


@login_required
def logout():
    verify_csrf()
    logout_user()
    flash('Desconectado com sucesso.', 'success')
    return redirect(url_for('index'))


def forgot_password():
    verify_csrf()
    email = (request.form.get('forgot_email') or request.form.get('email') or '').strip().lower()
    if not email:
        flash('Informe o e-mail para solicitar a redefinição.', 'error')
        return redirect(url_for('index'))
    user = User.query.filter_by(email=email).first()
    if user:
        # Marca como requer reset para o TI revisar
        user.reset_required = True
        db.session.commit()
    flash('Se o e-mail estiver cadastrado, a solicitação ficará disponível para revisão do TI.', 'success')
    return redirect(url_for('index'))


@login_required
def change_password():
    verify_csrf()
    current = request.form.get('current_password', '')
    newp = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')

    if not all([current, newp, confirm]):
        flash('Preencha todos os campos de senha.', 'error')
        return redirect(request.referrer or url_for('index'))

    # Verify current password
    if not current_user.check_password(current):
        flash('Senha atual incorreta.', 'error')
        return redirect(request.referrer or url_for('index'))

    if newp != confirm:
        flash('Nova senha e confirmação não correspondem.', 'error')
        return redirect(request.referrer or url_for('index'))

    if len(newp) < 6:
        flash('A nova senha deve ter ao menos 6 caracteres.', 'error')
        return redirect(request.referrer or url_for('index'))

    current_user.set_password(newp)
    current_user.reset_required = False
    db.session.commit()
    flash('Senha alterada com sucesso.', 'success')
    return redirect(request.referrer or url_for('index'))


def register_routes(app):
    app.add_url_rule('/register', methods=['GET', 'POST'], endpoint="register", view_func=register)
    app.add_url_rule('/login', methods=['GET', 'POST'], endpoint="login", view_func=login)
    app.add_url_rule('/logout', methods=['POST'], endpoint="logout", view_func=logout)
    app.add_url_rule('/forgot', methods=['POST'], endpoint="forgot_password", view_func=forgot_password)
    app.add_url_rule('/change_password', methods=['POST'], endpoint="change_password", view_func=change_password)
