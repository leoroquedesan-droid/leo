from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from datetime import datetime as dt
from sqlalchemy import exc
import os

app = Flask(__name__)
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
    pagamento = db.Column(db.Integer)
    cep = db.Column(db.String(10))
    endereco = db.Column(db.String(200))
    numero_casa = db.Column(db.String(10))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    login = db.Column(db.String(50))
    senha = db.Column(db.String(50))

class Salao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    local = db.Column(db.String(100), nullable=False)
    dia = db.Column(db.String(50), nullable=False)
    hora = db.Column(db.String(50), nullable=False)
    pagamento = db.Column(db.String(50), nullable=False)  # Forma de pagamento
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario = db.relationship('Usuario', backref='locacoes')
    valor_entrada = db.Column(db.Float, default=0.0)
    valor_segunda_parte = db.Column(db.Float, default=0.0)


class Login(db.Model):
    __tablename__ = 'login'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    senha = db.Column(db.String(80), nullable=False)


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
# ROTAS PRINCIPAIS E DASHBOARD
# -----------------------------
@app.route('/locacao/editar/<int:locacao_id>', methods=['GET', 'POST'])
def editar_locacao(locacao_id):
    # ... lógica de edição ...
    pass
@app.route('/locacao/excluir/<int:locacao_id>', methods=['POST'])
def excluir_locacao(locacao_id):
    # ... lógica de exclusão e redirect ...
    pass
# -----------------------------
# ROTAS PRINCIPAIS E DASHBOARD
# -----------------------------
def login_required(f):
    def wrap(*args, **kwargs):
        if 'login_id' not in session:
            flash("Você precisa estar logado para acessar esta página.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap # <--- CORRIGIDO: Agora ele retorna o 'wrap' e não chama a si mesmo.


@app.route('/index')
@login_required
def index():
    hoje = date.today()
    trinta_dias_atras = hoje - timedelta(days=30)

    # MÉTRICAS PARA OS CARDS (como mostrado em)
    total_usuarios = Usuario.query.count()
    novos_usuarios_30d = Usuario.query.filter(Usuario.data_registro >= trinta_dias_atras).count()
    atrasos_count = Usuario.query.filter(Usuario.pagamento < hoje).count()

    hoje_str = hoje.strftime('%Y-%m-%d')
    locacoes_futuras_count = Salao.query.filter(Salao.dia > hoje_str).count()

    proximos_locacoes = []
    locacoes = Salao.query.all()
    for loc in locacoes:
        try:
            data_loc = date.fromisoformat(loc.dia)
            if 0 <= (data_loc - hoje).days <= 3:
                proximos_locacoes.append(loc)
        except:
            pass

    return render_template('index.html',
                           proximos=proximos_locacoes,
                           total_usuarios=total_usuarios,
                           novos_usuarios_30d=novos_usuarios_30d,
                           atrasos_count=atrasos_count,
                           locacoes_futuras_count=locacoes_futuras_count)


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'login_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']
        usuario = Login.query.filter_by(nome=nome, senha=senha).first()
        if usuario:
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
        # Leitura de todos os campos (Corrigido NameError)
        nome = request.form["nome"]
        numero = request.form["numero"]
        idade = request.form["idade"]
        dia_pagamento = int(request.form["pagamento"])

        # Campos de Endereço (incluindo o novo: numero_casa)
        cep = request.form["cep"]
        rua = request.form["rua"]
        numero_casa = request.form["numero_casa"]
        bairro = request.form["bairro"]
        cidade = request.form["cidade"]
        estado = request.form["estado"]

        hoje = date.today()

        # Calcula o próximo vencimento
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
            nome=nome, numero=numero, cep=cep, rua=rua,
            numero_casa=numero_casa,  # Salva o novo campo
            bairro=bairro,
            cidade=cidade, estado=estado, idade=idade,
            pagamento=pagamento,
            data_registro=hoje
        )
        db.session.add(usuario)
        db.session.commit()
        flash("Usuário cadastrado com sucesso!", "success")
        return redirect(url_for("usuarios"))
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


# ROTAS DE EDIÇÃO E EXCLUSÃO (Corrigindo BuildError)
@app.route("/editar_usuario/<int:id>", methods=["GET", "POST"])
@login_required
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    if request.method == "POST":
        usuario.nome = request.form["nome"]
        usuario.numero = request.form["numero"]
        usuario.idade = request.form["idade"]
        usuario.cep = request.form["cep"]
        usuario.rua = request.form["rua"]
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

    # Exclui o usuário.
    db.session.delete(usuario)
    db.session.commit()
    flash(f"Usuário {usuario.nome} excluído com sucesso!", "success")
    return redirect(url_for("usuarios"))


# -----------------------------
# ROTAS DE LOCAÇÃO, PAGAMENTO E RELATÓRIO
# -----------------------------
@app.route("/locacao_salas")
@login_required
def locacao_salas():
    usuarios = Usuario.query.all()
    return render_template("saloes.html", usuarios=usuarios)


@app.route("/salvar_locacao", methods=["POST"])
@login_required
def salvar_locacao():
    salao_local = request.form["salao"]
    dia = request.form["dia"]
    pagamento = request.form["pagamento"]
    usuario_id = request.form["usuario"]

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


@app.route("/registrar_pagamento", methods=["GET", "POST"])
@login_required
def registrar_pagamento():
    usuarios = Usuario.query.all()
    if request.method == "POST":
        usuario_id = request.form["usuario"]
        data_pagamento = datetime.strptime(request.form["data_pagamento"], "%Y-%m-%d").date()
        proximo_pagamento = datetime.strptime(request.form["proximo_pagamento"], "%Y-%m-%d").date()

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

    mensalidades_atrasadas = Usuario.query.filter(Usuario.pagamento < hoje).order_by(Usuario.pagamento.asc()).all()

    mes_str = request.args.get('mes', hoje.strftime('%Y-%m'))
    try:
        ano = int(mes_str.split('-')[0])
        mes = int(mes_str.split('-')[1])
    except:
        ano = hoje.year
        mes = hoje.month
        mes_str = hoje.strftime('%Y-%m')

    # Filtra pagamentos pelo mês e ano (para relatórios de pagamentos pagos no mês)
    pagamentos_mes = Pagamento.query.join(Pagamento.usuario).filter(
        db.extract('year', Pagamento.data_pagamento) == ano,
        db.extract('month', Pagamento.data_pagamento) == mes
    ).order_by(Pagamento.data_pagamento.desc()).all()

    trinta_dias_atras = hoje - timedelta(days=30)
    novos_associados = Usuario.query.filter(Usuario.data_registro >= trinta_dias_atras).order_by(
        Usuario.data_registro.desc()).all()

    return render_template("relatorio_mensalidades.html",
                           atrasadas=mensalidades_atrasadas,
                           pagamentos_mes=pagamentos_mes,
                           novos_associados=novos_associados,
                           mes_selecionado=mes_str)


@app.route("/relatorio_locacoes")
@login_required
def relatorio_locacoes():
    locacoes = Salao.query.order_by(Salao.dia.desc()).all()
    return render_template("relatorio_locacoes.html", locacoes=locacoes)


@app.route("/chamados")
@login_required
def chamados():
    return render_template("chamados.html")


# -----------------------------
# SETUP INICIAL E EXECUÇÃO
# -----------------------------
def setup_initial_data(app):
    with app.app_context():
        # Cria as tabelas. Nota: Se o campo 'numero_casa' não existir na sua base atual,
        # você precisará deletar o arquivo 'meubanco.db' para que a nova coluna seja criada.
        db.create_all()
        # Adiciona usuários de login iniciais
        try:
            if not Login.query.first():
                logins = [
                    Login(nome='leo', senha='admin'),
                    Login(nome='Karine', senha='Karine'),
                    Login(nome='janaina', senha='janaina')
                ]
                db.session.add_all(logins)
                db.session.commit()
        except exc.OperationalError:
            pass



if __name__ == "__main__":
    # Obtém a porta do ambiente, caso contrário, usa 5000 (para testes locais)
    port = int(os.environ.get("PORT", 5000)) 
    
    # Roda o aplicativo, escutando em '0.0.0.0' para que seja acessível externamente
    app.run(host='0.0.0.0', port=port)
