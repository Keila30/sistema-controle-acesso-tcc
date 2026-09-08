import os

from flask import Flask, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")

usuarios = {
    "admin": {"senha": "1234", "perfil": "admin"},
    "operador": {"senha": "abcd", "perfil": "operador"}
}

# Lista de solicitações (simulação)
solicitacoes = []

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")

        if usuario in usuarios and usuarios[usuario]["senha"] == senha:
            session["usuario"] = usuario
            session["perfil"] = usuarios[usuario]["perfil"]
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

