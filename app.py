import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_bcrypt import Bcrypt
from functools import wraps
import sqlite3
from database import init_db, get_db_connection, create_default_categories


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-later")

# Added BY DEVIN ****
bcrypt = Bcrypt(app) #Initializing Bcrypt for hashing
# **************
# Added BY DEVIN *****
def login_required(f): 
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function
#****************
@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
# Added BY DEVIN *****
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if not email or not password:
            flash("Email and password are required.")
            return redirect(url_for("login"))
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user["password_hash"], password):
            session["user_id"] = user["user_id"]
            flash("Successfully logged in")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.")
            return redirect(url_for("login"))
    
    return render_template("login.html")
# *************************
# ADDED BY DEVIN ********
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        if not email or not password:
            flash("Email and password are required.")
            return redirect(url_for("register"))
            
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, hashed_pw)
            )
            new_user_id = cursor.lastrowid
            create_default_categories(conn, new_user_id)
            conn.commit()

            flash("Registration successful")
            return redirect(url_for('login'))
            
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("Email is already registered")
            return redirect(url_for('register'))
        except Exception:
            conn.rollback()
            flash("An error occurred during registration. Please try again.")
            return redirect(url_for('register'))
        finally:
            conn.close()
            
    return render_template('register.html')
#*******
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/transactions")
@login_required
def transactions():
    return render_template("transactions.html")

@app.route("/budgets")
@login_required
def budgets():
    return render_template("budgets.html")

@app.route("/reports")
@login_required
def reports():
    return render_template("reports.html")

@app.route("/logout")
def logout():
    session.clear() 
    flash("successfully logged out") 
    return redirect(url_for('login'))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)