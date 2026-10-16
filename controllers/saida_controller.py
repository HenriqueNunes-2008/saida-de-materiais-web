from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User, Employee, Project, MaterialOutput, Product, StockMovement
from services.estoque_service import register_output, search_active_products, StockValidationError
from controllers.estoque_controller import csrf_token, verify_csrf
from sqlalchemy import select
from services.legacy_service import get_nomes, get_projetos, get_report_suggestions, registrar_saida, gerar_excel
import secrets

def almoxarifado_required():
    if current_user.sector != 'Almoxarifado':
        flash('Acesso negado. Apenas o Almoxarifado pode alterar saídas.', 'error')
        return False
    return True

def index():
    # First screen: if not authenticated, show auth page (login / cadastro)
    if not current_user.is_authenticated:
        return render_template('auth.html')

    if current_user.sector == 'TI' or current_user.is_admin:
        return redirect(url_for('admin_panel'))

    if current_user.sector == 'Compras':
        return redirect(url_for('report'))

    # Somente usuários do setor Almoxarifado (ou admins) podem registrar saídas
    if request.method == "POST":
        if not current_user.is_authenticated or (not current_user.is_admin and current_user.sector != 'Almoxarifado'):
            flash('Apenas usuários do Almoxarifado (aprovados) podem registrar saídas. Faça login com conta adequada.', 'error')
            return redirect(url_for('index'))

        verify_csrf()
        nome = request.form.get("nome")
        projeto = request.form.get("projeto")
        product_id = request.form.get("product_id", "").strip()
        material = product_id
        quantidade = request.form.get("quantidade", "").strip()

        if not (nome and projeto and material and quantidade):
            flash("Preencha todos os campos!", "error")
            return redirect(url_for("index"))

        try:
            register_output(int(product_id), nome, projeto, quantidade, current_user.id)
        except (ValueError, StockValidationError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, StockValidationError) else 'Selecione um produto válido.', 'error')
            return redirect(url_for('index'))
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível registrar a saída. Tente novamente.", "error")
            return redirect(url_for("index"))

        flash("Saída registrada com sucesso!", "success")
        return redirect(url_for("index"))

    # Ao renderizar, permitir que Compras apenas visualize e baixe o Excel; Almoxarifado pode editar
    can_edit = False
    can_download = False
    if current_user.is_authenticated:
        if current_user.sector == 'Almoxarifado':
            can_edit = True
            can_download = True
        elif current_user.sector == 'Compras':
            can_download = True
        # TI (is_admin) does not get saída/report access in the main UI

    nomes_list = get_nomes()
    projetos_list = get_projetos()
    return render_template("index.html", nomes=nomes_list, projetos=projetos_list,
                           csrf_token=csrf_token(), current_user=current_user,
                           can_edit=can_edit, can_download=can_download, title='Saída de Materiais')


@login_required
def buscar_materiais():
    if current_user.sector != 'Almoxarifado' and not current_user.is_admin:
        return jsonify({'error': 'Acesso negado.'}), 403
    term = request.args.get('q', '').strip()
    if len(term) < 2:
        return jsonify({'items': []})
    try:
        products = search_active_products(term)
        return jsonify({'items': [{
            'id': p.id,
            'code': p.code,
            'description': p.description,
            'unit': p.stock_unit,
            'stock': str(p.stock_quantity),
            'price': str(p.last_unit_price) if p.last_unit_price is not None else None,
        } for p in products]})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({'error': 'Não foi possível buscar materiais agora.'}), 503


@login_required
def download_excel():
    # Apenas Almoxarifado e Compras podem baixar o Excel
    if current_user.sector not in ['Almoxarifado', 'Compras']:
        flash('Acesso negado ao download.', 'error')
        return redirect(url_for('index'))

    try:
        # Mês atual
        agora = datetime.now()
        inicio_mes = datetime(agora.year, agora.month, 1)

        # Primeiro dia do próximo mês
        if agora.month == 12:
            inicio_proximo_mes = datetime(agora.year + 1, 1, 1)
        else:
            inicio_proximo_mes = datetime(
                agora.year,
                agora.month + 1,
                1
            )

        # Busca somente os registros do mês atual no Neon
        material_outputs = (
            MaterialOutput.query
            .filter(
                MaterialOutput.created_at >= inicio_mes,
                MaterialOutput.created_at < inicio_proximo_mes
            )
            .order_by(MaterialOutput.created_at.asc())
            .all()
        )

        # Gera a planilha mensal
        excel_file = gerar_excel(material_outputs)

        nome_arquivo = (
            f"saida_materiais_"
            f"{agora.year}_"
            f"{agora.month:02}.xlsx"
        )

        return send_file(
            excel_file,
            as_attachment=True,
            download_name=nome_arquivo,
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    except SQLAlchemyError:
        db.session.rollback()
        flash(
            'Não foi possível gerar o arquivo Excel. '
            'Tente novamente.',
            'error'
        )
        return redirect(url_for('index'))


@login_required
def edit_output(output_id):
    if not almoxarifado_required():
        return redirect(url_for('report'))

    material_output = MaterialOutput.query.get_or_404(output_id)
    if material_output.product_id is not None:
        flash('Saídas com baixa automática são imutáveis. Para correções, registre um ajuste de estoque controlado.', 'error')
        return redirect(url_for('report'))

    if request.method == 'POST':
        verify_csrf()
        employee_name = request.form.get('employee_name', '').strip()
        project_name = request.form.get('project_name', '').strip()
        material = request.form.get('material', '').strip()
        quantity = request.form.get('quantity', '').strip()

        if not all([employee_name, project_name, material, quantity]):
            flash('Preencha todos os campos da saída.', 'error')
            return render_template(
                'edit_output.html',
                material_output=material_output,
                nomes=get_nomes(),
                projetos=get_projetos(),
                csrf_token=csrf_token(),
                title='Editar Saída',
            )

        try:
            quantity_int = int(quantity)
            if quantity_int <= 0:
                raise ValueError
        except ValueError:
            flash('Quantidade deve ser um número inteiro positivo.', 'error')
            return render_template(
                'edit_output.html',
                material_output=material_output,
                nomes=get_nomes(),
                projetos=get_projetos(),
                csrf_token=csrf_token(),
                title='Editar Saída',
            )

        material_output.employee_name = employee_name
        material_output.project_name = project_name
        material_output.material = material
        material_output.quantity = quantity_int

        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash('Não foi possível atualizar a saída. Tente novamente.', 'error')
            return render_template(
                'edit_output.html',
                material_output=material_output,
                nomes=get_nomes(),
                projetos=get_projetos(),
                csrf_token=csrf_token(),
                title='Editar Saída',
            )

        flash('Saída atualizada com sucesso.', 'success')
        return redirect(url_for('report'))

    return render_template(
        'edit_output.html',
        material_output=material_output,
        nomes=get_nomes(),
        projetos=get_projetos(),
        title='Editar Saída',
    )


@login_required
def delete_output(output_id):
    if not almoxarifado_required():
        return redirect(url_for('report'))

    material_output = MaterialOutput.query.get_or_404(output_id)
    if material_output.product_id is not None:
        flash('Saídas com baixa automática não podem ser excluídas. Use um ajuste auditável.', 'error')
        return redirect(url_for('report'))
    verify_csrf()
    try:
        db.session.delete(material_output)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash('Não foi possível excluir a saída. Tente novamente.', 'error')
        return redirect(url_for('report'))

    flash('Saída excluída com sucesso.', 'success')
    return redirect(url_for('report'))


def register_routes(app):
    app.add_url_rule("/", methods=["GET", "POST"], endpoint="index", view_func=index)
    app.add_url_rule('/api/materiais/busca', methods=['GET'], endpoint='buscar_materiais', view_func=buscar_materiais)
    app.add_url_rule('/download_excel', endpoint="download_excel", view_func=download_excel)
    app.add_url_rule('/saida/<int:output_id>/editar', methods=['GET', 'POST'], endpoint="edit_output", view_func=edit_output)
    app.add_url_rule('/saida/<int:output_id>/excluir', methods=['POST'], endpoint="delete_output", view_func=delete_output)
