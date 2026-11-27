import io  # permite entregar o PDF que está no banco como se fosse um arquivo
import os  # acessar variáveis de ambiente
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv  # carregar variáveis de ambiente do arquivo .env
load_dotenv()

from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from extensions import db
from models import Arquivo, Solicitacao, Usuario

# ---------------------------------------------------------------
# Configurações do Flask
# ---------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://controle:controle_dev@localhost:5432/controle_acesso",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # limite de 16MB por arquivo
db.init_app(app)


# ---------------------------------------------------------------
# Banco de dados: cria as tabelas e os usuários iniciais
# ---------------------------------------------------------------
def inicializar_banco() -> None:
    db.create_all()

    usuarios_iniciais = (
        ("admin", os.environ.get("ADMIN_PASSWORD", "1234"), "admin"),
        ("operador", os.environ.get("OPERADOR_PASSWORD", "abcd"), "operador"),
    )

    for nome, senha, perfil in usuarios_iniciais:
        if db.session.scalar(db.select(Usuario).filter_by(nome=nome)) is None:
            db.session.add(
                Usuario(
                    nome=nome,
                    senha_hash=generate_password_hash(senha),
                    perfil=perfil,
                )
            )

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


with app.app_context():
    inicializar_banco()


# ---------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------
def usuario_logado():
    """Devolve o usuário que está logado (ou None)."""
    if "usuario" not in session:
        return None
    return db.session.scalar(db.select(Usuario).filter_by(nome=session["usuario"]))


def pode_ver_arquivo_da_solicitacao(solicitacao, usuario):
    """Admin vê qualquer uma. Operador só as próprias solicitações já aprovadas."""
    if usuario.perfil == "admin":
        return True
    return solicitacao.usuario_id == usuario.id and solicitacao.status == "aprovado"


def enviar_pdf(arquivo, baixar):
    """Entrega o PDF guardado no banco: baixar=True baixa, baixar=False abre no navegador."""
    return send_file(
        io.BytesIO(bytes(arquivo.conteudo)),
        mimetype="application/pdf",
        as_attachment=baixar,
        download_name=arquivo.nome_arquivo,
    )


@app.template_filter("data_br")
def data_br(valor):
    """Mostra data e hora no horário de Brasília."""
    if valor is None:
        return ""
    return valor.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")


@app.template_filter("tamanho")
def tamanho(bytes_):
    """Mostra o tamanho do arquivo de forma legível (KB ou MB)."""
    if bytes_ < 1024 * 1024:
        return f"{max(1, round(bytes_ / 1024))} KB"
    return f"{bytes_ / (1024 * 1024):.1f} MB".replace(".", ",")


@app.errorhandler(413)
def arquivo_muito_grande(_erro):
    flash("Arquivo muito grande. O limite é de 16 MB.", "error")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------
# Login e logout
# ---------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        usuario_encontrado = db.session.scalar(
            db.select(Usuario).filter_by(nome=usuario)
        )

        if usuario_encontrado and usuario_encontrado.verificar_senha(senha):
            session["usuario"] = usuario_encontrado.nome
            session["perfil"] = usuario_encontrado.perfil
            return redirect(url_for("dashboard"))

        flash("Usuário ou senha inválidos.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------
# Painel: admin vê todas as solicitações, operador vê só as suas
# ---------------------------------------------------------------
@app.route("/dashboard")
def dashboard():
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for("login"))

    consulta = db.select(Solicitacao).order_by(Solicitacao.id.desc())
    if usuario.perfil == "operador":
        consulta = consulta.where(Solicitacao.usuario_id == usuario.id)
    solicitacoes = db.session.scalars(consulta).all()

    # biblioteca de mapas (o conteúdo do PDF não é carregado aqui, só nome e tamanho)
    arquivos = db.session.scalars(db.select(Arquivo).order_by(Arquivo.nome_arquivo)).all()

    return render_template(
        "dashboard.html",
        usuario=usuario.nome,
        perfil=usuario.perfil,
        solicitacoes=solicitacoes,
        arquivos=arquivos,
    )


# ---------------------------------------------------------------
# Admin: cadastra um PDF na biblioteca (uma única vez)
# ---------------------------------------------------------------
@app.route("/biblioteca/enviar", methods=["POST"])
def enviar_para_biblioteca():
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for("login"))

    if usuario.perfil != "admin":
        flash("Apenas administradores podem cadastrar arquivos.", "error")
        return redirect(url_for("dashboard"))

    pdf = request.files.get("arquivo")
    if not pdf or pdf.filename == "":
        flash("Nenhum arquivo selecionado.", "error")
        return redirect(url_for("dashboard"))

    nome = secure_filename(pdf.filename)
    if not nome.lower().endswith(".pdf"):
        flash("Apenas arquivos PDF são permitidos.", "error")
        return redirect(url_for("dashboard"))

    conteudo = pdf.read()
    if not conteudo.startswith(b"%PDF-"):
        flash("O arquivo enviado não parece ser um PDF válido.", "error")
        return redirect(url_for("dashboard"))

    ja_existe = db.session.scalar(db.select(Arquivo.id).where(Arquivo.nome_arquivo == nome))
    if ja_existe:
        flash("Já existe um arquivo com esse nome na biblioteca.", "error")
        return redirect(url_for("dashboard"))

    db.session.add(
        Arquivo(
            nome_arquivo=nome,
            tipo_arquivo="pdf",
            tamanho_bytes=len(conteudo),
            conteudo=conteudo,
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Já existe um arquivo com esse nome na biblioteca.", "error")
        return redirect(url_for("dashboard"))

    flash("Arquivo adicionado à biblioteca.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------
# Admin: exclui um arquivo da biblioteca (só se ninguém solicitou)
# ---------------------------------------------------------------
@app.route("/biblioteca/<int:arquivo_id>/excluir", methods=["POST"])
def excluir_da_biblioteca(arquivo_id):
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for("login"))

    if usuario.perfil != "admin":
        flash("Apenas administradores podem excluir arquivos.", "error")
        return redirect(url_for("dashboard"))

    arquivo = db.session.get(Arquivo, arquivo_id)
    if arquivo is None:
        flash("Arquivo não encontrado.", "error")
        return redirect(url_for("dashboard"))

    em_uso = db.session.scalar(
        db.select(Solicitacao.id).where(Solicitacao.arquivo_id == arquivo.id).limit(1)
    )
    if em_uso:
        flash("Este arquivo já tem solicitações e não pode ser excluído.", "error")
        return redirect(url_for("dashboard"))

    db.session.delete(arquivo)
    db.session.commit()

    flash("Arquivo excluído da biblioteca.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------
# Admin: pré-visualiza qualquer arquivo da biblioteca
# ---------------------------------------------------------------
@app.route("/arquivos/<int:arquivo_id>/visualizar")
def visualizar_arquivo(arquivo_id):
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for("login"))

    if usuario.perfil != "admin":
        flash("Arquivo indisponível.", "error")
        return redirect(url_for("dashboard"))

    arquivo = db.session.get(Arquivo, arquivo_id)
    if arquivo is None:
        flash("Arquivo não encontrado.", "error")
        return redirect(url_for("dashboard"))

    return enviar_pdf(arquivo, baixar=False)


# ---------------------------------------------------------------
# Operador: solicita um arquivo da biblioteca (nasce como "pendente")
# ---------------------------------------------------------------
@app.route("/solicitar", methods=["POST"])
def solicitar():
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for("login"))

    if usuario.perfil != "operador":
        flash("Apenas operadores podem fazer solicitações.", "error")
        return redirect(url_for("dashboard"))

    arquivo_id = request.form.get("arquivo_id", type=int)
    arquivo = db.session.get(Arquivo, arquivo_id) if arquivo_id else None
    if arquivo is None:
        flash("Escolha um arquivo da lista.", "error")
        return redirect(url_for("dashboard"))

    pendente = db.session.scalar(
        db.select(Solicitacao.id).where(
            Solicitacao.usuario_id == usuario.id,
            Solicitacao.arquivo_id == arquivo.id,
            Solicitacao.status == "pendente",
        )
    )
    if pendente:
        flash("Você já tem uma solicitação pendente para este arquivo.", "error")
        return redirect(url_for("dashboard"))

    db.session.add(
        Solicitacao(
            usuario_id=usuario.id,
            arquivo_id=arquivo.id,
            descricao=arquivo.nome_arquivo,
        )
    )
    db.session.commit()

    flash("Solicitação registrada.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------
# Admin: aprova ou nega uma solicitação pendente
# ---------------------------------------------------------------
@app.route("/solicitacoes/<int:solicitacao_id>/decidir", methods=["POST"])
def decidir_solicitacao(solicitacao_id):
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for("login"))

    if usuario.perfil != "admin":
        flash("Apenas administradores podem aprovar ou negar.", "error")
        return redirect(url_for("dashboard"))

    solicitacao = db.session.get(Solicitacao, solicitacao_id)
    if solicitacao is None:
        flash("Solicitação não encontrada.", "error")
        return redirect(url_for("dashboard"))

    if solicitacao.status != "pendente":
        flash("Essa solicitação já foi respondida.", "error")
        return redirect(url_for("dashboard"))

    acao = request.form.get("acao")
    if acao == "aprovar":
        solicitacao.status = "aprovado"
        mensagem = "Solicitação aprovada."
    elif acao == "negar":
        solicitacao.status = "negado"
        mensagem = "Solicitação negada."
    else:
        flash("Ação inválida.", "error")
        return redirect(url_for("dashboard"))

    db.session.commit()
    flash(mensagem, "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------
# Operador: visualiza o PDF aprovado no navegador (não conta como download)
# ---------------------------------------------------------------
@app.route("/solicitacoes/<int:solicitacao_id>/visualizar")
def visualizar_solicitacao(solicitacao_id):
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for("login"))

    solicitacao = db.session.get(Solicitacao, solicitacao_id)
    if solicitacao is None or not pode_ver_arquivo_da_solicitacao(solicitacao, usuario):
        flash("Arquivo indisponível.", "error")
        return redirect(url_for("dashboard"))

    return enviar_pdf(solicitacao.arquivo, baixar=False)


# ---------------------------------------------------------------
# Operador: baixa o PDF aprovado (o sistema registra data e hora do download)
# ---------------------------------------------------------------
@app.route("/solicitacoes/<int:solicitacao_id>/baixar")
def baixar_solicitacao(solicitacao_id):
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for("login"))

    solicitacao = db.session.get(Solicitacao, solicitacao_id)
    if solicitacao is None or not pode_ver_arquivo_da_solicitacao(solicitacao, usuario):
        flash("Arquivo indisponível.", "error")
        return redirect(url_for("dashboard"))

    if usuario.perfil == "operador" and solicitacao.baixado_em is None:
        solicitacao.baixado_em = datetime.now(timezone.utc)
        db.session.commit()

    return enviar_pdf(solicitacao.arquivo, baixar=True)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
