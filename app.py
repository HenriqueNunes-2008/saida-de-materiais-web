from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import csv
from openpyxl import Workbook, load_workbook  # type: ignore
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side  # type: ignore
from datetime import datetime, timedelta
import os
import secrets
from dotenv import load_dotenv

load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_hex(16)
DATABASE_URL = os.getenv('DATABASE_URL')  # e.g., postgres://...
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
# Configure SQLAlchemy: use provided DATABASE_URL (Neon) or fallback to sqlite for local dev
if DATABASE_URL:
    # Heroku/Neon-style URLs may need adjustments for SQLAlchemy
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

ARQUIVO_SAIDA = "saida_materiais.csv"
ARQUIVO_NOMES = "nomes.txt"
ARQUIVO_PROJETOS = "projetos.txt"

# Configurações de Estilo Globais (usadas para Excel)
BORDER_THIN = Border(left=Side(style='thin'), right=Side(style='thin'), 
                    top=Side(style='thin'), bottom=Side(style='thin'))
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
HEADER_FILL = PatternFill(start_color="0066CC", end_color="0066CC", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF")

# --- Models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    sector = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    active = db.Column(db.Boolean, default=False)
    approved = db.Column(db.Boolean, default=False)
    reset_required = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

# --- Additional Models ---
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)
    sector = db.Column(db.String(80))

class MaterialOutput(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.TIMESTAMP(timezone=True), server_default=db.func.now(), nullable=False)
    employee_name = db.Column(db.Text, nullable=False)
    project_name = db.Column(db.Text)
    material = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey('user.id'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Utility functions ---
def obter_nome_arquivo_excel():
    agora = datetime.now()
    return f"saida_materiais_{agora.year}_{agora.month:02}.xlsx"

def carregar_lista(arquivo, padrao):
    # Backward-compatible loader: when DATABASE_URL is set, read from DB tables instead of flat files
    if DATABASE_URL:
        # If using DB, prefer employees/projects tables
        return []
    if not os.path.exists(arquivo):
        with open(arquivo, "w", encoding="utf-8") as f:
            f.write("\n".join(padrao))
    with open(arquivo, "r", encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip()]

# Helper functions to get names and projects from DB when available
def get_nomes():
    if DATABASE_URL:
        try:
            return [e.name for e in Employee.query.order_by(Employee.name).all()]
        except Exception:
            return []
    else:
        nomes = carregar_lista(ARQUIVO_NOMES, ["João", "Maria", "Carlos", "Fernanda"])
        nomes.sort()
        return nomes

def get_projetos():
    if DATABASE_URL:
        try:
            return [p.name for p in Project.query.order_by(Project.name).all()]
        except Exception:
            return []
    else:
        projetos = carregar_lista(ARQUIVO_PROJETOS, ["Projeto A", "Projeto B", "Projeto C"])
        projetos.sort()
        return projetos


def get_report_suggestions():
    suggestion_map = {'projects': [], 'materials': [], 'employees': []}
    try:
        projects = db.session.query(MaterialOutput.project_name).filter(MaterialOutput.project_name.isnot(None)).distinct().order_by(MaterialOutput.project_name).all()
        suggestion_map['projects'] = [item[0] for item in projects if item[0]]

        materials = db.session.query(MaterialOutput.material).filter(MaterialOutput.material.isnot(None)).distinct().order_by(MaterialOutput.material).all()
        suggestion_map['materials'] = [item[0] for item in materials if item[0]]

        employees = db.session.query(MaterialOutput.employee_name).filter(MaterialOutput.employee_name.isnot(None)).distinct().order_by(MaterialOutput.employee_name).all()
        suggestion_map['employees'] = [item[0] for item in employees if item[0]]
    except Exception:
        suggestion_map = {'projects': [], 'materials': [], 'employees': []}
    return suggestion_map


def registrar_em_excel(dados):
    nome_arquivo = obter_nome_arquivo_excel()

    if not os.path.exists(nome_arquivo):
        wb = Workbook()
        ws = wb.active
        ws.title = "Saídas"

        # Cabeçalhos
        headers = ["Data/Hora", "Nome", "Projeto", "Material", "Quantidade"]
        ws.append(headers)
        
        # Formatar cabeçalhos usando constantes
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = BORDER_THIN
            ws.column_dimensions[cell.column_letter].width = 25

    else:
        wb = load_workbook(nome_arquivo)
        ws = wb["Saídas"]

    nova_linha = ws.max_row + 1
    for col, valor in enumerate(dados, start=1):
        cell = ws.cell(row=nova_linha, column=col, value=valor)
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_THIN

    wb.save(nome_arquivo)

    # If using DB, also persist the output record
    if DATABASE_URL:
        try:
            # recorded_by could be determined by current_user if available
            recorded_by = current_user.id if current_user.is_authenticated else None
            emp_name = dados[1]
            proj_name = dados[2]
            material = dados[3]
            quantidade = int(dados[4])
            mo = MaterialOutput(employee_name=emp_name, project_name=proj_name, material=material, quantity=quantidade, recorded_by=recorded_by)
            db.session.add(mo)
            db.session.commit()
        except Exception as e:
            # Do not break the user flow if DB insert fails; log to console
            print('Erro ao persistir saída no DB:', e)

# --- Routes ---
@app.route("/", methods=["GET", "POST"])
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

        nome = request.form.get("nome")
        projeto = request.form.get("projeto")
        material = request.form.get("material", "").strip()
        quantidade = request.form.get("quantidade", "").strip()

        if not (nome and projeto and material and quantidade):
            flash("Preencha todos os campos!", "error")
            return redirect(url_for("index"))

        try:
            quantidade_int = int(quantidade)
            if quantidade_int <= 0:
                raise ValueError
        except ValueError:
            flash("Quantidade deve ser um número inteiro positivo!", "error")
            return redirect(url_for("index"))

        data = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        registro = [data, nome, projeto, material, quantidade]

        registrar_em_excel(registro)  # Grava no Excel

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
    return render_template("index.html", nomes=nomes_list, projetos=projetos_list, current_user=current_user, can_edit=can_edit, can_download=can_download, title='Saída de Materiais')


@app.route('/download_excel')
@login_required
def download_excel():
    # Apenas Almoxarifado e Compras aprovados podem baixar o arquivo xlsx
    if not (current_user.sector in ['Almoxarifado', 'Compras']):
        flash('Acesso negado ao download.', 'error')
        return redirect(url_for('index'))

    arquivo = obter_nome_arquivo_excel()
    if not os.path.exists(arquivo):
        flash('Arquivo Excel não encontrado.', 'error')
        return redirect(url_for('index'))

    from flask import send_file
    return send_file(arquivo, as_attachment=True)

# --- Lists and helper endpoints (names / projects) ---
@app.route('/add_nome', methods=['POST'])
def add_nome():
    novo_nome = request.form.get('novo_nome', '').strip()
    if not novo_nome:
        flash('Nome não pode ser vazio.', 'error')
        return redirect(url_for('index'))

    if DATABASE_URL:
        # Persist to DB
        existing = Employee.query.filter_by(name=novo_nome).first()
        if existing:
            flash('Esse nome já existe.', 'error')
        else:
            emp = Employee(name=novo_nome)
            db.session.add(emp)
            db.session.commit()
            flash(f"Nome '{novo_nome}' adicionado com sucesso!", 'success')
    else:
        global nomes
        if novo_nome in nomes:
            flash('Esse nome já existe.', 'error')
        else:
            with open(ARQUIVO_NOMES, 'a', encoding='utf-8') as f:
                f.write(novo_nome + '\n')
            nomes.append(novo_nome)
            nomes.sort()
            flash(f"Nome '{novo_nome}' adicionado com sucesso!", 'success')
    return redirect(url_for('index'))

@app.route('/add_projeto', methods=['POST'])
def add_projeto():
    novo_projeto = request.form.get('novo_projeto', '').strip()
    if not novo_projeto:
        flash('Projeto não pode ser vazio.', 'error')
        return redirect(url_for('index'))

    if DATABASE_URL:
        existing = Project.query.filter_by(name=novo_projeto).first()
        if existing:
            flash('Esse projeto já existe.', 'error')
        else:
            p = Project(name=novo_projeto)
            db.session.add(p)
            db.session.commit()
            flash(f"Projeto '{novo_projeto}' adicionado com sucesso!", 'success')
    else:
        global projetos
        if novo_projeto in projetos:
            flash('Esse projeto já existe.', 'error')
        else:
            with open(ARQUIVO_PROJETOS, 'a', encoding='utf-8') as f:
                f.write(novo_projeto + '\n')
            projetos.append(novo_projeto)
            projetos.sort()
            flash(f"Projeto '{novo_projeto}' adicionado com sucesso!", 'success')
    return redirect(url_for('index'))

@app.route('/delete_nome/<nome>', methods=['POST'])
def delete_nome(nome):
    if DATABASE_URL:
        emp = Employee.query.filter_by(name=nome).first()
        if emp:
            db.session.delete(emp)
            db.session.commit()
            flash(f"Nome '{nome}' removido com sucesso!", 'success')
        else:
            flash('Nome não encontrado.', 'error')
    else:
        global nomes
        if nome in nomes:
            nomes.remove(nome)
            with open(ARQUIVO_NOMES, 'w', encoding='utf-8') as f:
                for n in nomes:
                    f.write(n + '\n')
            flash(f"Nome '{nome}' removido com sucesso!", 'success')
        else:
            flash('Nome não encontrado.', 'error')
    return redirect(url_for('view_lists'))

@app.route('/delete_projeto/<projeto>', methods=['POST'])
def delete_projeto(projeto):
    if DATABASE_URL:
        p = Project.query.filter_by(name=projeto).first()
        if p:
            db.session.delete(p)
            db.session.commit()
            flash(f"Projeto '{projeto}' removido com sucesso!", 'success')
        else:
            flash('Projeto não encontrado.', 'error')
    else:
        global projetos
        if projeto in projetos:
            projetos.remove(projeto)
            with open(ARQUIVO_PROJETOS, 'w', encoding='utf-8') as f:
                for pr in projetos:
                    f.write(pr + '\n')
            flash(f"Projeto '{projeto}' removido com sucesso!", 'success')
        else:
            flash('Projeto não encontrado.', 'error')
    return redirect(url_for('view_lists'))

@app.route('/view_lists')
def view_lists():
    if DATABASE_URL:
        nomes_db = get_nomes()
        projetos_db = get_projetos()
        return render_template('view_lists.html', nomes=nomes_db, projetos=projetos_db)
    else:
        return render_template('view_lists.html', nomes=nomes, projetos=projetos)

@app.route('/register', methods=['GET', 'POST'])
def register():
    # existing register handler (unchanged)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        sector = request.form.get('sector', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not all([name, sector, email, password]):
            flash('Preencha todos os campos do cadastro.', 'error')
            return redirect(url_for('index'))

        if User.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.', 'error')
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Usuário não encontrado.', 'error')
            return redirect(url_for('index'))
        if not user.approved:
            flash('Conta ainda precisa ser aprovada pelo TI.', 'error')
            return redirect(url_for('index'))
        if not user.active:
            flash('Conta está desativada. Contate o TI.', 'error')
            return redirect(url_for('index'))
        if not user.check_password(password):
            flash('Senha incorreta.', 'error')
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

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Desconectado com sucesso.', 'success')
    return redirect(url_for('index'))

@app.route('/forgot', methods=['POST'])
def forgot_password():
    email = (request.form.get('forgot_email') or request.form.get('email') or '').strip().lower()
    if not email:
        flash('Informe o e-mail para solicitar a redefinição.', 'error')
        return redirect(url_for('index'))
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('E-mail não cadastrado.', 'error')
        return redirect(url_for('index'))
    # Marca como requer reset para o TI revisar
    user.reset_required = True
    db.session.commit()
    flash('Solicitação enviada. O TI receberá alerta para redefinir a senha.', 'success')
    return redirect(url_for('index'))


@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
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

# --- TI Admin Panel ---
@app.route('/admin')
@login_required
def admin_panel():
    # Allow TI sector or explicit admin flag
    if not (current_user.is_admin or current_user.sector == 'TI'):
        flash('Acesso negado. Apenas TI pode acessar este painel.', 'error')
        return redirect(url_for('index'))
    users = User.query.order_by(User.id.desc()).all()
    return render_template('admin.html', users=users)

@app.route('/admin/approve/<int:user_id>', methods=['POST'])
@login_required
def admin_approve(user_id):
    if not (current_user.is_admin or current_user.sector == 'TI'):
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    user.approved = True
    user.active = True
    db.session.commit()
    flash(f'Usuário {user.email} aprovado e ativado.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/toggle_active/<int:user_id>', methods=['POST'])
@login_required
def admin_toggle_active(user_id):
    if not (current_user.is_admin or current_user.sector == 'TI'):
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    user.active = not user.active
    db.session.commit()
    flash(f"Usuário {user.email} agora está {'ativo' if user.active else 'bloqueado'}.", 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/reset_password/<int:user_id>', methods=['POST'])
@login_required
def admin_reset_password(user_id):
    if not (current_user.is_admin or current_user.sector == 'TI'):
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    new_password = secrets.token_urlsafe(8)
    user.set_password(new_password)
    user.reset_required = False
    db.session.commit()
    # Show the new password to the TI (they should communicate it securely)
    flash(f'Senha redefinida para {user.email}. Senha temporária: {new_password}', 'success')
    return redirect(url_for('admin_panel'))

# --- Utility: create DB and default admin if env provided ---
with app.app_context():
    db.create_all()
    if ADMIN_EMAIL and ADMIN_PASSWORD:
        admin = User.query.filter_by(email=ADMIN_EMAIL.lower()).first()
        if not admin:
            admin = User(name='Admin', sector='TI', email=ADMIN_EMAIL.lower(), is_admin=True, approved=True, active=True)
            admin.set_password(ADMIN_PASSWORD)
            db.session.add(admin)
            db.session.commit()

@app.route('/report')
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
        suggestions=suggestions,
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


if __name__ == "__main__":
    app.run(debug=True)
