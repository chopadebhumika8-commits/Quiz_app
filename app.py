from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import time
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

DB_PATH = "database.db"

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- CREATE TABLES ----------------
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

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        db = get_db()
        try:
            db.execute("INSERT INTO users VALUES (?,?)", (u, generate_password_hash(p)))
            db.commit()
            return redirect("/")
        except:
            return "User already exists"

    return render_template("signup.html")

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()

        if user and check_password_hash(user["password"], p):
            session.clear()
            session["user"] = u
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid Login")

    return render_template("login.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html")

# ---------------- QUIZ ----------------
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
        session["start"] = time.time()

    i = session["index"]

    if request.method == "POST":
        selected = request.form.get("answer")
        correct = questions[i]["correct"]

        if selected == correct:
            session["score"] += 1

        session["index"] += 1
        return redirect(f"/quiz/{subject}/{type}")

    if i >= len(questions):
        score = session["score"]
        total = len(questions)
        time_taken = int(time.time() - session["start"])

        db.execute(
            "INSERT INTO results (username, score, total, time_taken) VALUES (?,?,?,?)",
            (session["user"], score, total, time_taken)
        )
        db.commit()

        session.pop("index")
        session.pop("score")
        session.pop("start")

        return redirect(url_for("result", score=score, total=total))

    return render_template("quiz.html", question=questions[i])

# ---------------- RESULT ----------------
@app.route("/result")
def result():
    score = int(request.args.get("score", 0))
    total = int(request.args.get("total", 0))

    db = get_db()

    users = db.execute("""
        SELECT username, score, time_taken
        FROM results
        ORDER BY score DESC, time_taken ASC
    """).fetchall()

    rank = 1
    for u in users:
        if u["username"] == session.get("user") and u["score"] == score:
            break
        rank += 1

    return render_template("result.html",
        score=score,
        total=total,
        rank=rank
    )

# ---------------- LEADERBOARD ----------------
@app.route("/leaderboard")
def leaderboard():
    if "user" not in session:
        return redirect("/")

    db = get_db()

    users = db.execute("""
        SELECT username, score, total, time_taken
        FROM results
        ORDER BY score DESC, time_taken ASC
    """).fetchall()

    return render_template("leaderboard.html", users=users)

# ---------------- PROFILE ----------------
@app.route("/profile")
def profile():
    if "user" not in session:
        return redirect("/")

    db = get_db()

    history = db.execute(
        "SELECT score,total FROM results WHERE username=?",
        (session["user"],)
    ).fetchall()

    total_quiz = len(history)
    total_score = sum(h["score"] for h in history)
    total_marks = sum(h["total"] for h in history)

    percentage = int((total_score / total_marks) * 100) if total_marks else 0

    return render_template("profile.html",
        user=session["user"],
        total_quiz=total_quiz,
        percentage=percentage
    )

# ---------------- CERTIFICATE ----------------
@app.route("/certificate")
def certificate():
    if "user" not in session:
        return redirect("/")

    db = get_db()

    last = db.execute("""
        SELECT score FROM results
        WHERE username=?
        ORDER BY id DESC LIMIT 1
    """, (session["user"],)).fetchone()

    score = last["score"] if last else 0

    return render_template("certificate.html",
        user=session["user"],
        score=score
    )

# ---------------- ADMIN LOGIN ----------------
@app.route("/admin_login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "admin123":
            session.clear()
            session["admin"] = True
            return redirect("/admin")

        return render_template("admin_login.html", error="Invalid Login")

    return render_template("admin_login.html")

# ---------------- ADMIN PANEL ----------------
@app.route("/admin", methods=["GET","POST"])
def admin():
    if "admin" not in session:
        return redirect("/admin_login")

    db = get_db()

    if request.method == "POST":
        db.execute("""
        INSERT INTO questions
        (subject,type,question,option1,option2,option3,option4,correct)
        VALUES (?,?,?,?,?,?,?,?)
        """, (
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

# ---------------- DELETE ----------------
@app.route("/delete/<int:id>")
def delete(id):
    if "admin" not in session:
        return redirect("/admin_login")

    db = get_db()
    db.execute("DELETE FROM questions WHERE id=?", (id,))
    db.commit()
    return redirect("/admin")

# ---------------- EDIT ----------------
@app.route("/edit/<int:id>", methods=["GET","POST"])
def edit(id):
    if "admin" not in session:
        return redirect("/admin_login")

    db = get_db()

    if request.method == "POST":
        db.execute("""
        UPDATE questions SET
        question=?, option1=?, option2=?, option3=?, option4=?, correct=?
        WHERE id=?
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

# ---------------- ADMIN LOGOUT ----------------
@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    return render_template("admin_logout.html")

# ---------------- USER LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
