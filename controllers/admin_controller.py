"""Gerencia usuarios, aprovacoes e operacoes administrativas autorizadas."""

from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file, make_response
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User, Employee, Project, MaterialOutput
import secrets
from controllers.estoque_controller import csrf_token, verify_csrf

@login_required
def admin_panel():
    # Permite acesso ao setor de TI ou a usuarios com autorizacao administrativa.
    if not (current_user.is_admin or current_user.sector == 'TI'):
        flash('Acesso negado. Apenas TI pode acessar este painel.', 'error')
        return redirect(url_for('index'))
    users = User.query.order_by(User.id.desc()).all()
    return render_template('admin.html', users=users, csrf_token=csrf_token())


@login_required
def admin_approve(user_id):
    verify_csrf()
    if not (current_user.is_admin or current_user.sector == 'TI'):
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    user.approved = True
    user.active = True
    db.session.commit()
    flash(f'Usuário {user.email} aprovado e ativado.', 'success')
    return redirect(url_for('admin_panel'))


@login_required
def admin_toggle_active(user_id):
    verify_csrf()
    if not (current_user.is_admin or current_user.sector == 'TI'):
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    user.active = not user.active
    db.session.commit()
    flash(f"Usuário {user.email} agora está {'ativo' if user.active else 'bloqueado'}.", 'success')
    return redirect(url_for('admin_panel'))


@login_required
def admin_reset_password(user_id):
    verify_csrf()
    if not (current_user.is_admin or current_user.sector == 'TI'):
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    new_password = secrets.token_urlsafe(8)
    user.set_password(new_password)
    user.reset_required = False
    db.session.commit()
    # Evita enviar credenciais por flash ou pelo cookie de sessao do navegador.
    users = User.query.order_by(User.id.desc()).all()
    response = make_response(render_template(
        'admin.html', users=users, csrf_token=csrf_token(),
        reset_credential={'email': user.email, 'password': new_password}
    ))
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


def register_routes(app):
    app.add_url_rule('/admin', endpoint="admin_panel", view_func=admin_panel)
    app.add_url_rule('/admin/approve/<int:user_id>', methods=['POST'], endpoint="admin_approve", view_func=admin_approve)
    app.add_url_rule('/admin/toggle_active/<int:user_id>', methods=['POST'], endpoint="admin_toggle_active", view_func=admin_toggle_active)
    app.add_url_rule('/admin/reset_password/<int:user_id>', methods=['POST'], endpoint="admin_reset_password", view_func=admin_reset_password)
