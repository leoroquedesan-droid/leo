from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta
from datetime import datetime as dt
from sqlalchemy import exc
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# NUNCA use uma chave secreta como esta em produção! Use variáveis de ambiente.
app.secret_key = "uma_chave_secreta_aqui_123"

# Configuração do banco (SQLite)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meubanco.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


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
    endereco = db.Column(db.String(200))  # Campo correto para o endereço/rua
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
# ROTAS PRINCIPAIS E DASHBOARD
# -----------------------------
@app.route('/index')
@login_required
def index():
    hoje = date.today()

    # Dados para cards principais (apenas os mantidos)
    total_usuarios = Usuario.query.count()
    # Atrasos: pagamento não nulo E pagamento anterior a hoje
    atrasos_count = Usuario.query.filter(Usuario.pagamento != None, Usuario.pagamento < hoje).count()

    # Dados para a lista "Próximas Locações (3 Dias)"
    proximos_locacoes = []
    locacoes = Salao.query.all()
    for loc in locacoes:
        try:
            data_loc = date.fromisoformat(loc.dia)
            if 0 <= (data_loc - hoje).days <= 3:
                proximos_locacoes.append(loc)
        except:
            pass  # Ignora locações com data inválida

    return render_template('index.html',
                           proximos=proximos_locacoes,
                           total_usuarios=total_usuarios,
                           atrasos_count=atrasos_count)


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
# ROTAS DE CADASTRO E GESTÃO
# -----------------------------
@app.route("/cadastro_usuario", methods=["GET", "POST"])
@login_required
def cadastro():
    if request.method == "POST":
        # Usando .get() para aumentar a robustez e evitar KeyError
        try:
            # Campos obrigatórios
            nome = request.form["nome"]
            data_nascimento = request.form["data_nascimento"]
            cpf = request.form["cpf"]
            rg = request.form["rg"]
            dependentes = request.form["dependentes"]
            numero = request.form["numero"]
            dia_pagamento = int(request.form["pagamento"])

            # Campos de endereço (usando .get() para segurança)
            cep = request.form.get("cep")
            endereco = request.form.get("endereco")  # Correção: lendo 'endereco'
            numero_casa = request.form.get("numero_casa")
            bairro = request.form.get("bairro")
            cidade = request.form.get("cidade")
            estado = request.form.get("estado")

        except KeyError as e:
            flash(f"Erro: Campo obrigatório do formulário ausente ({e}).", "danger")
            return redirect(url_for("cadastro"))

        hoje = date.today()
        # Lógica de cálculo de pagamento
        try:
            if dia_pagamento >= hoje.day:
                pagamento = date(hoje.year, hoje.month, dia_pagamento)
            else:
                if hoje.month == 12:
                    pagamento = date(hoje.year + 1, 1, dia_pagamento)
                else:
                    pagamento = date(hoje.year, hoje.month + 1, dia_pagamento)
        except ValueError:
            flash("Dia de pagamento inválido ou data não existe. Por favor, ajuste.", "danger")
            return redirect(url_for("cadastro"))

        usuario = Usuario(
            nome=nome,
            data_nascimento=data_nascimento,
            cpf=cpf,
            rg=rg,
            dependentes=dependentes,
            numero=numero,
            pagamento=pagamento,
            cep=cep,
            endereco=endereco,
            numero_casa=numero_casa,
            bairro=bairro,
            cidade=cidade,
            estado=estado,
            data_registro=hoje
        )
        db.session.add(usuario)
        try:
            db.session.commit()
            flash("Usuário cadastrado com sucesso!", "success")
            return redirect(url_for("usuarios"))
        except exc.IntegrityError:
            flash("Erro ao cadastrar. Verifique se o usuário já existe.", "danger")
            db.session.rollback()
        except Exception as e:
            flash(f"Erro inesperado ao salvar: {e}", "danger")
            db.session.rollback()

    return render_template("cadastro_usuario.html")


@app.route("/usuarios")
@login_required
def usuarios():
    nome_pesquisa = request.args.get('nome')
    if nome_pesquisa:
        lista = Usuario.query.filter(Usuario.nome.ilike(f"%{nome_pesquisa}%")).all()
    else:
        lista = Usuario.query.all()
    return render_template("usuarios.html", usuarios=lista)


@app.route("/editar_usuario/<int:id>", methods=["GET", "POST"])
@login_required
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    if request.method == "POST":
        usuario.nome = request.form["nome"]
        usuario.data_nascimento = request.form["data_nascimento"]
        usuario.cpf = request.form["cpf"]
        usuario.rg = request.form["rg"]
        usuario.dependentes = request.form["dependentes"]
        usuario.numero = request.form["numero"]
        usuario.cep = request.form["cep"]
        usuario.endereco = request.form["endereco"]
        usuario.numero_casa = request.form["numero_casa"]
        usuario.bairro = request.form["bairro"]
        usuario.cidade = request.form["cidade"]
        usuario.estado = request.form["estado"]
        try:
            db.session.commit()
            flash(f"Usuário {usuario.nome} atualizado com sucesso!", "success")
            return redirect(url_for("usuarios"))
        except Exception as e:
            flash(f"Erro ao salvar: {e}", "danger")
            db.session.rollback()
    return render_template("editar_usuario.html", usuario=usuario)


@app.route("/excluir_usuario/<int:id>")
@login_required
def excluir_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash(f"Usuário {usuario.nome} excluído com sucesso!", "success")
    return redirect(url_for("usuarios"))


# -----------------------------
# ROTAS DE LOCAÇÃO
# -----------------------------
@app.route("/locacao_salas")
@login_required
def locacao_salas():
    usuarios = Usuario.query.all()
    return render_template("saloes.html", usuarios=usuarios)


@app.route("/salvar_locacao", methods=["POST"])
@login_required
def salvar_locacao():
    # USANDO .get() PARA ROBUSTEZ: Corrigindo o KeyError
    salao_local = request.form.get("salao", "")
    dia = request.form.get("dia", "")
    pagamento = request.form.get("pagamento", "")
    usuario_id = request.form.get("usuario", None)

    if not salao_local or not usuario_id or not dia:
        flash("Os campos Local, Dia e Usuário são obrigatórios para a locação.", "danger")
        return redirect(url_for("locacao_salas"))

    valor_entrada = request.form.get("valor_entrada", 0.0)
    valor_segunda_parte = request.form.get("valor_segunda_parte", 0.0)

    try:
        entrada_float = float(valor_entrada)
        segunda_parte_float = float(valor_segunda_parte)
    except ValueError:
        flash("Os valores de pagamento devem ser números válidos.", "danger")
        return redirect(url_for("locacao_salas"))

    nova_locacao = Salao(
        local=salao_local, dia=dia, hora="", pagamento=pagamento, usuario_id=usuario_id,
        valor_entrada=entrada_float, valor_segunda_parte=segunda_parte_float
    )
    db.session.add(nova_locacao)
    db.session.commit()
    flash("Locação cadastrada com sucesso!", "success")
    return redirect(url_for("relatorio_locacoes"))


@app.route("/locacao/editar/<int:locacao_id>", methods=['GET', 'POST'])
@login_required
def editar_locacao(locacao_id):
    locacao = Salao.query.get_or_404(locacao_id)
    usuarios = Usuario.query.all()

    if request.method == 'POST':
        locacao.local = request.form["salao"]
        locacao.dia = request.form["dia"]
        locacao.pagamento = request.form["pagamento"]
        locacao.usuario_id = request.form["usuario"]

        valor_entrada = request.form.get("valor_entrada", 0.0)
        valor_segunda_parte = request.form.get("valor_segunda_parte", 0.0)

        try:
            locacao.valor_entrada = float(valor_entrada)
            locacao.valor_segunda_parte = float(valor_segunda_parte)
            db.session.commit()
            flash("Locação atualizada com sucesso!", "success")
            return redirect(url_for('relatorio_locacoes'))
        except ValueError:
            flash("Os valores de pagamento devem ser números válidos.", "danger")
        except Exception as e:
            flash(f"Erro ao salvar: {e}", "danger")
            db.session.rollback()

    return render_template('editar_locacao.html', locacao=locacao, usuarios=usuarios)


@app.route('/locacao/excluir/<int:locacao_id>', methods=['GET', 'POST'])
@login_required
def excluir_locacao(locacao_id):
    locacao = Salao.query.get_or_404(locacao_id)

    try:
        db.session.delete(locacao)
        db.session.commit()
        flash(f"Locação do dia {locacao.dia} excluída com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao excluir locação: {e}", "danger")
        db.session.rollback()

    return redirect(url_for('relatorio_locacoes'))


@app.route("/relatorio_locacoes")
@login_required
def relatorio_locacoes():
    locacoes = Salao.query.order_by(Salao.dia.desc()).all()
    return render_template("relatorio_locacoes.html", locacoes=locacoes)


# -----------------------------
# ROTAS DE PAGAMENTO E RELATÓRIO DE MENSALIDADES
# -----------------------------
@app.route("/registrar_pagamento", methods=["GET", "POST"])
@login_required
def registrar_pagamento():
    usuarios = Usuario.query.all()
    if request.method == "POST":
        usuario_id = request.form["usuario"]
        data_pagamento = dt.strptime(request.form["data_pagamento"], "%Y-%m-%d").date()
        proximo_pagamento = dt.strptime(request.form["proximo_pagamento"], "%Y-%m-%d").date()
        pagamento = Pagamento(
            usuario_id=usuario_id,
            data_pagamento=data_pagamento,
            proximo_pagamento=proximo_pagamento
        )
        db.session.add(pagamento)
        usuario = Usuario.query.get(usuario_id)
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
            usuario_id_int = int(usuario_id)
            query = query.filter_by(usuario_id=usuario_id_int)
        except ValueError:
            usuario_id = None
    pagamentos = query.all()
    return render_template("pagamentos.html",
                           pagamentos=pagamentos,
                           todos_usuarios=todos_usuarios,
                           usuario_selecionado=usuario_id)


@app.route("/relatorio_mensalidades")
@login_required
def relatorio_mensalidades():
    hoje = date.today()

    # 1. PEGAR PARÂMETROS DE PESQUISA (implementação da busca por nome)
    nome_pesquisa = request.args.get('nome_pesquisa')
    mes_str = request.args.get('mes', hoje.strftime('%Y-%m'))

    # 2. QUERY BASE: FILTROS GERAIS
    atrasadas_query = Usuario.query.filter(
        Usuario.pagamento != None,
        Usuario.pagamento < hoje
    )
    novos_associados_query = Usuario.query.filter(
        Usuario.data_registro >= hoje - timedelta(days=30)
    )

    # 3. FILTRO POR NOME (se houver pesquisa, aplicar a todas as listas)
    if nome_pesquisa:
        atrasadas_query = atrasadas_query.filter(
            Usuario.nome.ilike(f"%{nome_pesquisa}%")
        )
        novos_associados_query = novos_associados_query.filter(
            Usuario.nome.ilike(f"%{nome_pesquisa}%")
        )

    mensalidades_atrasadas = atrasadas_query.order_by(Usuario.pagamento.asc()).all()
    novos_associados = novos_associados_query.order_by(Usuario.data_registro.desc()).all()

    # 4. FILTRO DE PAGAMENTOS DO MÊS
    try:
        ano = int(mes_str.split('-')[0])
        mes = int(mes_str.split('-')[1])
    except:
        ano = hoje.year
        mes = hoje.month
        mes_str = hoje.strftime('%Y-%m')

    pagamentos_mes_query = Pagamento.query.join(Pagamento.usuario).filter(
        db.extract('year', Pagamento.data_pagamento) == ano,
        db.extract('month', Pagamento.data_pagamento) == mes
    )

    # Adiciona filtro de nome aos pagamentos do mês
    if nome_pesquisa:
        pagamentos_mes_query = pagamentos_mes_query.filter(
            Usuario.nome.ilike(f"%{nome_pesquisa}%")
        )

    pagamentos_mes = pagamentos_mes_query.order_by(Pagamento.data_pagamento.desc()).all()

    return render_template("relatorio_mensalidades.html",
                           atrasadas=mensalidades_atrasadas,
                           pagamentos_mes=pagamentos_mes,
                           novos_associados=novos_associados,
                           mes_selecionado=mes_str,
                           nome_pesquisa=nome_pesquisa)  # Passa o termo de pesquisa de volta


# -----------------------------
# OUTRAS ROTAS
# -----------------------------
@app.route("/chamados")
@login_required
def chamados():
    return render_template("chamados.html")


# -----------------------------
# SETUP INICIAL E EXECUÇÃO
# -----------------------------
def setup_initial_data(app):
    with app.app_context():
        db.create_all()
        try:
            if not Login.query.first():
                leo = Login(nome='leo')
                leo.set_password('admin')
                karine = Login(nome='Karine')
                karine.set_password('Karine')
                janaina = Login(nome='janaina')
                janaina.set_password('janaina')
                db.session.add_all([leo, karine, janaina])
                db.session.commit()
                print("Usuários de login iniciais criados com hash de senha.")
        except exc.OperationalError as e:
            print(f"ATENÇÃO: Não foi possível configurar os logins iniciais. Verifique o meubanco.db. Erro: {e}")
            db.session.rollback()
        except exc.IntegrityError:
            db.session.rollback()
            pass


if __name__ == "__main__":
    setup_initial_data(app)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)