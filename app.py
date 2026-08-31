from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "chave_secreta_tcc"

usuarios = {
    "admin": {"senha": "1234", "perfil": "admin"},
    "operador": {"senha": "abcd", "perfil": "operador"}
}

# Lista de solicitações (simulação)
solicitacoes = []

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        if usuario in usuarios and usuarios[usuario]["senha"] == senha:
            session["usuario"] = usuario
            session["perfil"] = usuarios[usuario]["perfil"]
            return redirect(url_for("dashboard"))
        else:
            return "Usuário ou senha inválidos"

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

    if session["perfil"] == "operador":
        pedido = request.form["pedido"]
        solicitacoes.append({
            "usuario": session["usuario"],
            "pedido": pedido
        })

    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)

