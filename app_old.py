from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "supersecretkey"  # session key

# Demo credentials
USERS = {
    "admin": "in123",
    "manager": "1234",
    "user": "12345"
}

@app.route("/")
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=session["user"])

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in USERS and USERS[username] == password:
            session["user"] = username
            return redirect(url_for("sln_terminus"))
        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

@app.route("/sln_terminus")
def sln_terminus():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("sln_terminus.html", user=session["user"])

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
