from flask import Flask, render_template, request, redirect, session
import sqlite3
import time
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret123")

# ---------------- DATABASE ----------------
DB_PATH = "database.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- CREATE TABLES ----------------
def create_tables():
    db = get_db()

    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT
    )
    """)

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

create_tables()

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        if not u or not p:
            return "Fill all fields"

        db = get_db()
        try:
            db.execute("INSERT INTO users VALUES (?, ?)",
                       (u, generate_password_hash(p)))
            db.commit()
            return redirect("/")
        except:
            return "User already exists"

    return render_template("signup.html")

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

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
    if not session.get("user"):
        return redirect("/")
    return render_template("dashboard.html", user=session["user"])

# ---------------- SELECT CLASS ----------------
@app.route("/select_class")
def select_class():
    if not session.get("user"):
        return redirect("/")
    return render_template("select_class.html")

# ---------------- PROFILE ----------------
@app.route("/profile")
def profile():
    if not session.get("user"):
        return redirect("/")
    return render_template("profile.html", user=session["user"])

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- QUIZ ----------------
@app.route("/quiz/<subject>/<type>", methods=["GET", "POST"])
def quiz(subject, type):
    if not session.get("user"):
        return redirect("/")

    db = get_db()

    questions = db.execute("""
        SELECT * FROM questions
        WHERE LOWER(subject)=LOWER(?) AND LOWER(type)=LOWER(?)
    """, (subject, type)).fetchall()

    if len(questions) == 0:
        return "No questions found"

    # ---------------- INIT QUIZ ----------------
    if "index" not in session:
        session["index"] = 0
        session["score"] = 0
        session["answers"] = []
        session["start_time"] = time.time()
        session["time_limit"] = 600   # 10 minutes

    index = session["index"]

    # ---------------- TIMER CHECK ----------------
    elapsed = time.time() - session["start_time"]
    remaining = session["time_limit"] - int(elapsed)

    if remaining <= 0:
        score = session["score"]
        total = len(questions)

        db.execute("""
            INSERT INTO results (username, score, total, time_taken)
            VALUES (?, ?, ?, ?)
        """, (session["user"], score, total, int(elapsed)))
        db.commit()

        session["final_answers"] = session["answers"]

        session.clear()

        return redirect(f"/result?score={score}&total={total}")

    # ---------------- ANSWER SUBMIT ----------------
    if request.method == "POST":
        selected = request.form.get("answer")

        if selected == questions[index]["correct"]:
            session["score"] += 1

        session["answers"].append({
            "question": questions[index]["question"],
            "selected": selected,
            "correct": questions[index]["correct"]
        })

        session["index"] += 1
        return redirect(request.url)

    # ---------------- QUIZ END ----------------
    if index >= len(questions):
        score = session["score"]
        total = len(questions)
        time_taken = int(elapsed)

        db.execute("""
            INSERT INTO results (username, score, total, time_taken)
            VALUES (?, ?, ?, ?)
        """, (session["user"], score, total, time_taken))
        db.commit()

        session["final_answers"] = session["answers"]

        session.clear()

        return redirect(f"/result?score={score}&total={total}")

    q = questions[index]
    progress = int((index / len(questions)) * 100)

    return render_template(
        "quiz.html",
        question=q,
        progress=progress,
        time_left=remaining
    )

# ---------------- RESULT ----------------
@app.route("/result")
def result():
    return render_template(
        "result.html",
        score=request.args.get("score"),
        total=request.args.get("total"),
        answers=session.get("final_answers", []),
        time_taken=session.get("time_taken", 0)
    )

# ---------------- LEADERBOARD ----------------
@app.route("/leaderboard")
def leaderboard():
    if not session.get("user"):
        return redirect("/")

    db = get_db()

    data = db.execute("""
        SELECT username, score, total, time_taken
        FROM results
        ORDER BY score DESC, time_taken ASC
        LIMIT 10
    """).fetchall()

    return render_template("leaderboard.html", data=data)

# ---------------- ADMIN LOGIN ----------------
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        if u == ADMIN_USER and p == ADMIN_PASS:
            session["admin"] = True
            return redirect("/admin")

        return "Invalid Admin Login"

    return render_template("admin_login.html")

# ---------------- ADMIN PANEL ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect("/admin_login")

    db = get_db()

    if request.method == "POST":
        db.execute("""
            INSERT INTO questions (subject, type, question, option1, option2, option3, option4, correct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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

    questions = db.execute("SELECT * FROM questions ORDER BY id DESC").fetchall()

    return render_template("admin_panel.html", questions=questions)

# ---------------- DELETE ----------------
@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("admin"):
        return redirect("/admin_login")

    db = get_db()
    db.execute("DELETE FROM questions WHERE id=?", (id,))
    db.commit()

    return redirect("/admin")

# ---------------- EDIT ----------------
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if not session.get("admin"):
        return redirect("/admin_login")

    db = get_db()
    q = db.execute("SELECT * FROM questions WHERE id=?", (id,)).fetchone()

    if request.method == "POST":
        db.execute("""
            UPDATE questions
            SET subject=?, type=?, question=?, option1=?, option2=?, option3=?, option4=?, correct=?
            WHERE id=?
        """, (
            request.form["subject"],
            request.form["type"],
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

    return render_template("edit.html", q=q)

# ---------------- DEBUG ----------------
@app.route("/debug")
def debug():
    return "App is working!"

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
