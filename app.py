from flask import Flask, render_template, request, redirect, session
import sqlite3
import time
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret123")

# ADMIN
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# DATABASE
DB_PATH = os.path.join(os.getcwd(), "database.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# CREATE TABLES
@app.before_request
def create_tables():
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
    db.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT,
        type TEXT,
        question TEXT,
        option1 TEXT,
        option2 TEXT,
        option3 TEXT,
        option4 TEXT,
        correct TEXT
    )
    """)
    db.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        score INTEGER,
        total INTEGER,
        time_taken INTEGER
    )
    """)
    db.commit()

# SIGNUP
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()

        db = get_db()
        try:
            db.execute("INSERT INTO users VALUES (?,?)", (u, generate_password_hash(p)))
            db.commit()
            return redirect("/")
        except:
            return "User already exists"

    return render_template("signup.html")

# LOGIN
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()

        if user and check_password_hash(user["password"], p):
            session.clear()
            session["user"] = u
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid Login")

    return render_template("login.html")

# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html")

# GO DASHBOARD (FROM ADMIN)
@app.route("/go_dashboard")
def go_dashboard():
    session.pop("admin", None)
    return redirect("/dashboard")

# SELECT
@app.route("/select_class")
def select_class():
    if "user" not in session:
        return redirect("/")
    return render_template("select_class.html")

@app.route("/select_type/<subject>")
def select_type(subject):
    if "user" not in session:
        return redirect("/")
    return render_template("select_type.html", subject=subject)

# QUIZ
@app.route("/quiz/<subject>/<type>", methods=["GET","POST"])
def quiz(subject, type):
    if "user" not in session:
        return redirect("/")

    db = get_db()
    questions = db.execute(
        "SELECT * FROM questions WHERE subject=? AND type=?",
        (subject, type)
    ).fetchall()

    if not questions:
        return "No questions available"

    if "index" not in session:
        session["index"] = 0
        session["score"] = 0
        session["answers"] = []
        session["start_time"] = time.time()

    index = session["index"]

    if request.method == "POST":
        selected = request.form.get("answer")
        correct = questions[index]["correct"]

        session["answers"].append({
            "question": questions[index]["question"],
            "selected": selected,
            "correct": correct
        })

        if selected == correct:
            session["score"] += 1

        session["index"] += 1
        return redirect(f"/quiz/{subject}/{type}")

    if index >= len(questions):
        score = session["score"]
        total = len(questions)
        time_taken = int(time.time() - session["start_time"])

        db.execute(
            "INSERT INTO results VALUES (NULL,?,?,?,?)",
            (session["user"], score, total, time_taken)
        )
        db.commit()

        session["final_answers"] = session["answers"]
        session["time_taken"] = time_taken

        session.clear()
        return redirect(f"/result?score={score}&total={total}")

    q = questions[index]
    progress = int((index / len(questions)) * 100)

    return render_template("quiz.html", question=q, progress=progress, time_left=60)

# RESULT
@app.route("/result")
def result():
    return render_template("result.html",
        score=int(request.args.get("score", 0)),
        total=int(request.args.get("total", 0)),
        answers=session.get("final_answers", []),
        time_taken=session.get("time_taken", 0)
    )

# LEADERBOARD
@app.route("/leaderboard")
def leaderboard():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    users = db.execute("SELECT * FROM results ORDER BY score DESC").fetchall()

    return render_template("leaderboard.html", users=users)

# ADMIN LOGIN
@app.route("/admin_login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USERNAME and request.form["password"] == ADMIN_PASSWORD:
            session.clear()
            session["admin"] = True
            return redirect("/admin")

        return render_template("admin_login.html", error="Invalid Admin Login")

    return render_template("admin_login.html")

# ADMIN PANEL
@app.route("/admin", methods=["GET","POST"])
def admin():
    if "admin" not in session:
        return redirect("/admin_login")

    db = get_db()

    if request.method == "POST":
        db.execute("INSERT INTO questions VALUES (NULL,?,?,?,?,?,?,?)", (
            request.form["subject"],
            request.form["type"],
            request.form["question"],
            request.form["o1"],
            request.form["o2"],
            request.form["o3"],
            request.form["o4"],
            request.form["correct"]
        ))
        db.commit()

    questions = db.execute("SELECT * FROM questions").fetchall()
    return render_template("admin.html", questions=questions)

# DELETE
@app.route("/delete/<int:id>")
def delete(id):
    db = get_db()
    db.execute("DELETE FROM questions WHERE id=?", (id,))
    db.commit()
    return redirect("/admin")

# EDIT
@app.route("/edit/<int:id>", methods=["GET","POST"])
def edit(id):
    db = get_db()

    if request.method == "POST":
        db.execute("""
        UPDATE questions SET question=?, option1=?, option2=?, option3=?, option4=?, correct=? WHERE id=?
        """, (
            request.form["question"],
            request.form["o1"],
            request.form["o2"],
            request.form["o3"],
            request.form["o4"],
            request.form["correct"],
            id
        ))
        db.commit()
        return redirect("/admin")

    q = db.execute("SELECT * FROM questions WHERE id=?", (id,)).fetchone()
    return render_template("edit.html", q=q)

# ADMIN LOGOUT
@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    return render_template("admin_logout.html")

# USER LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# RUN
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
