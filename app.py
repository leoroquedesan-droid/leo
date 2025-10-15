from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta
from datetime import datetime as dt
from sqlalchemy import exc
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "uma_chave_secreta_aqui_123"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meubanco.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# -----------------------------
# FUNÇÃO AUXILIAR PARA O JINJA2
# -----------------------------
def today_iso():
    return date.today().isoformat()

app.jinja_env.globals.update(today_iso=today_iso)

# -----------------------------
# MODELOS (TABELAS)
# -----------------------------
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data_nascimento = db.Column(db.String(20))
    cpf = db.Column(db.String(20))
    rg = db.Column(db.String(20))
    dependentes = db.Column(db.Text)
    numero = db.Column(db.String(20))
    pagamento = db.Column(db.Date)
    cep = db.Column(db.String(10))
    endereco = db.Column(db.String(200))
    numero_casa = db.Column(db.String(10))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    login = db.Column(db.String(50))
    senha = db.Column(db.String(50))
    data_registro = db.Column(db.Date, default=date.today)


class Salao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    local = db.Column(db.String(100), nullable=False)
    dia = db.Column(db.String(50), nullable=False)
    hora = db.Column(db.String(50), nullable=False)
    pagamento = db.Column(db.String(50), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario = db.relationship('Usuario', backref='locacoes')
    valor_entrada = db.Column(db.Float, default=0.0)
    valor_segunda_parte = db.Column(db.Float, default=0.0)


class Login(db.Model):
    __tablename__ = 'login'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False, unique=True)
    senha_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.senha_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.senha_hash, password)


class Pagamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario = db.relationship('Usuario', backref='pagamentos')
    data_pagamento = db.Column(db.Date, nullable=False)
    proximo_pagamento = db.Column(db.Date, nullable=False)
    valor_pago = db.Column(db.Float, nullable=False, default=0.0)
    referente = db.Column(db.String(100), nullable=True)  # Ex: "Mensalidade Outubro"


class Chamado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assunto = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    solicitante = db.Column(db.String(100), nullable=False)
    data_registro = db.Column(db.DateTime, default=dt.utcnow)
    status = db.Column(db.String(50), default='Aberto')

# -----------------------------
# FUNÇÕES AUXILIARES
# -----------------------------
def login_required(f):
    def wrap(*args, **kwargs):
        if 'login_id' not in session:
            flash("Você precisa estar logado para acessar esta página.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# -----------------------------
# ROTAS PRINCIPAIS
# -----------------------------
@app.route('/index')
@login_required
def index():
    hoje = date.today()
    total_usuarios = Usuario.query.count()
    atrasos_count = Usuario.query.filter(Usuario.pagamento != None, Usuario.pagamento < hoje).count()
    proximos_locacoes = []
    locacoes = Salao.query.all()
    for loc in locacoes:
        try:
            data_loc = date.fromisoformat(loc.dia)
            if 0 <= (data_loc - hoje).days <= 3:
                proximos_locacoes.append(loc)
        except:
            pass
    return render_template('index.html', proximos=proximos_locacoes,
                           total_usuarios=total_usuarios, atrasos_count=atrasos_count)

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'login_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        nome = request.form['nome']
        senha_digitada = request.form['senha']
        usuario = Login.query.filter_by(nome=nome).first()
        if usuario and usuario.check_password(senha_digitada):
            session['login_id'] = usuario.id
            session['login_nome'] = usuario.nome
            flash(f"Bem-vindo, {usuario.nome}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Usuário ou senha incorretos!", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Você foi desconectado com sucesso.", "success")
    return redirect(url_for('login'))

# -----------------------------
# CADASTRO DE USUÁRIOS
# -----------------------------
@app.route("/cadastro_usuario", methods=["GET", "POST"])
@login_required
def cadastro():
    if request.method == "POST":
        try:
            nome = request.form["nome"]
            data_nascimento = request.form["data_nascimento"]
            cpf = request.form["cpf"]
            rg = request.form["rg"]
            dependentes = request.form["dependentes"]
            numero = request.form["numero"]
            dia_pagamento = int(request.form["pagamento"])
            cep = request.form.get("cep")
            endereco = request.form.get("endereco")
            numero_casa = request.form.get("numero_casa")
            bairro = request.form.get("bairro")
            cidade = request.form.get("cidade")
            estado = request.form.get("estado")
        except KeyError as e:
            flash(f"Erro: Campo obrigatório ausente ({e}).", "danger")
            return redirect(url_for("cadastro"))
        hoje = date.today()
        try:
            if dia_pagamento >= hoje.day:
                pagamento = date(hoje.year, hoje.month, dia_pagamento)
            else:
                if hoje.month == 12:
                    pagamento = date(hoje.year + 1, 1, dia_pagamento)
                else:
                    pagamento = date(hoje.year, hoje.month + 1, dia_pagamento)
        except ValueError:
            flash("Dia de pagamento inválido.", "danger")
            return redirect(url_for("cadastro"))

        usuario = Usuario(nome=nome, data_nascimento=data_nascimento, cpf=cpf, rg=rg,
                          dependentes=dependentes, numero=numero, pagamento=pagamento,
                          cep=cep, endereco=endereco, numero_casa=numero_casa, bairro=bairro,
                          cidade=cidade, estado=estado, data_registro=hoje)
        db.session.add(usuario)
        try:
            db.session.commit()
            flash("Usuário cadastrado com sucesso!", "success")
            return redirect(url_for("usuarios"))
        except exc.IntegrityError:
            flash("Erro: Usuário já existe.", "danger")
            db.session.rollback()
        except Exception as e:
            flash(f"Erro inesperado: {e}", "danger")
            db.session.rollback()
    return render_template("cadastro_usuario.html")

@app.route("/usuarios")
@login_required
def usuarios():
    nome_pesquisa = request.args.get('nome')
    lista = Usuario.query.filter(Usuario.nome.ilike(f"%{nome_pesquisa}%")).all() if nome_pesquisa else Usuario.query.all()
    return render_template("usuarios.html", usuarios=lista, hoje=date.today())

# -----------------------------
# PAGAMENTOS
# -----------------------------
@app.route("/registrar_pagamento", methods=["GET", "POST"])
@login_required
def registrar_pagamento():
    usuarios = Usuario.query.all()
    if request.method == "POST":
        usuario_id = request.form["usuario"]
        try:
            data_pagamento = dt.strptime(request.form["data_pagamento"], "%Y-%m-%d").date()
            proximo_pagamento = dt.strptime(request.form["proximo_pagamento"], "%Y-%m-%d").date()
        except ValueError:
            flash("Erro no formato de data.", "danger")
            return redirect(url_for("registrar_pagamento"))

        valor_pago = float(request.form.get("valor_pago", 0.0))
        referente = request.form.get("referente", "")

        pagamento = Pagamento(usuario_id=usuario_id,
                              data_pagamento=data_pagamento,
                              proximo_pagamento=proximo_pagamento,
                              valor_pago=valor_pago,
                              referente=referente)
        db.session.add(pagamento)
        usuario = Usuario.query.get(usuario_id)
        if usuario:
            usuario.pagamento = proximo_pagamento
        db.session.commit()
        flash(f"Pagamento registrado para {usuario.nome}!", "success")
        return redirect(url_for("listar_pagamentos"))
    return render_template("registrar_pagamento.html", usuarios=usuarios)

@app.route("/listar_pagamentos")
@login_required
def listar_pagamentos():
    todos_usuarios = Usuario.query.all()
    usuario_id = request.args.get('usuario_id')
    query = Pagamento.query.order_by(Pagamento.data_pagamento.desc())
    if usuario_id:
        try:
            query = query.filter_by(usuario_id=int(usuario_id))
        except ValueError:
            pass
    pagamentos = query.all()
    return render_template("pagamentos.html",
                           pagamentos=pagamentos,
                           todos_usuarios=todos_usuarios,
                           usuario_selecionado=usuario_id)

# -----------------------------
# RELATÓRIO DE MENSALIDADES
# -----------------------------
@app.route("/relatorio_mensalidades")
@login_required
def relatorio_mensalidades():
    hoje = date.today()
    nome_pesquisa = request.args.get('nome_pesquisa')
    mes_str = request.args.get('mes', hoje.strftime('%Y-%m'))
    atrasadas_query = Usuario.query.filter(Usuario.pagamento != None, Usuario.pagamento < hoje)
    novos_associados_query = Usuario.query.filter(Usuario.data_registro >= hoje - timedelta(days=30))
    if nome_pesquisa:
        atrasadas_query = atrasadas_query.filter(Usuario.nome.ilike(f"%{nome_pesquisa}%"))
        novos_associados_query = novos_associados_query.filter(Usuario.nome.ilike(f"%{nome_pesquisa}%"))
    mensalidades_atrasadas = atrasadas_query.order_by(Usuario.pagamento.asc()).all()
    novos_associados = novos_associados_query.order_by(Usuario.data_registro.desc()).all()
    try:
        ano, mes = map(int, mes_str.split('-'))
    except:
        ano, mes = hoje.year, hoje.month
        mes_str = hoje.strftime('%Y-%m')
    pagamentos_mes_query = Pagamento.query.join(Pagamento.usuario).filter(
        db.extract('year', Pagamento.data_pagamento) == ano,
        db.extract('month', Pagamento.data_pagamento) == mes)
    if nome_pesquisa:
        pagamentos_mes_query = pagamentos_mes_query.filter(Usuario.nome.ilike(f"%{nome_pesquisa}%"))
    pagamentos_mes = pagamentos_mes_query.order_by(Pagamento.data_pagamento.desc()).all()
    return render_template("relatorio_mensalidades.html",
                           atrasadas=mensalidades_atrasadas,
                           pagamentos_mes=pagamentos_mes,
                           novos_associados=novos_associados,
                           mes_selecionado=mes_str,
                           nome_pesquisa=nome_pesquisa)

# -----------------------------
# SETUP INICIAL
# -----------------------------
def setup_initial_data(app):
    with app.app_context():
        db.create_all()
        try:
            if not Login.query.first():
                leo = Login(nome='leo'); leo.set_password('admin')
                karine = Login(nome='Karine'); karine.set_password('Karine')
                janaina = Login(nome='janaina'); janaina.set_password('janaina')
                db.session.add_all([leo, karine, janaina])
                db.session.commit()
                print("Usuários de login criados com sucesso.")
        except exc.OperationalError as e:
            print(f"Erro ao configurar logins iniciais: {e}")
            db.session.rollback()

if __name__ == "__main__":
    setup_initial_data(app)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
