from flask import Flask, render_template, redirect, url_for, request, flash
from database import init_db
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-later")

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        flash("Login logic will be implemented in Sprint 1.")
        return redirect(url_for("login"))
    
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        flash("Registration logic will be implemented in Sprint 1.")
        return redirect(url_for("register"))
    
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/transactions")
def transactions():
    return render_template("transactions.html")

@app.route("/budgets")
def budgets():
    return render_template("budgets.html")

@app.route("/reports")
def reports():
    return render_template("reports.html")

@app.route("/logout")
def logout():
    flash("Logout logic will be implemented in Sprint 1.")
    return redirect(url_for("login"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)