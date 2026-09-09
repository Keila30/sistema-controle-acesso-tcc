import os

from flask import Flask, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from extensions import db
from models import Usuario

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://controle:controle_dev@localhost:5432/controle_acesso",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)


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

# Lista de solicitações (simulação)
solicitacoes = []

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

@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        usuario=session["usuario"],
        perfil=session["perfil"],
        solicitacoes=solicitacoes
    )

@app.route("/solicitar", methods=["POST"])
def solicitar():
    if "usuario" not in session:
        return redirect(url_for("login"))

    if session["perfil"] != "operador":
        flash("Apenas operadores podem fazer solicitações.", "error")
        return redirect(url_for("dashboard"))

    pedido = request.form.get("pedido", "").strip()
    if not pedido:
        flash("Informe o arquivo solicitado.", "error")
        return redirect(url_for("dashboard"))

    solicitacoes.append({
        "usuario": session["usuario"],
        "pedido": pedido
    })
    flash("Solicitação registrada.", "success")

    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")

