from flask import Flask, render_template, request, redirect, session
import sqlite3
import time
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ---------------- SECURITY ----------------
app.secret_key = os.environ.get("SECRET_KEY", "secret123")

# ---------------- DATABASE ----------------
DB_PATH = os.path.join(os.getcwd(), "database.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# CREATE TABLES ALWAYS (IMPORTANT FOR RENDER)
@app.before_request
def create_tables():
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT, type TEXT, question TEXT, option1 TEXT, option2 TEXT, option3 TEXT, option4 TEXT, correct TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, score INTEGER, total INTEGER, time_taken INTEGER)")
    db.commit()

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        if not u or not p:
            return "Fill all fields"

        hashed = generate_password_hash(p)

        db = get_db()
        try:
            db.execute("INSERT INTO users VALUES (?,?)", (u, hashed))
            db.commit()
            return redirect("/")
        except:
            return "User already exists"

    return render_template("signup.html")

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET","POST"])
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
        else:
            return render_template("login.html", error="Invalid Login")

    return render_template("login.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html", user=session["user"])

# ---------------- QUIZ ----------------
@app.route("/quiz/<subject>/<type>", methods=["GET","POST"])
def quiz(subject, type):
    if "user" not in session:
        return redirect("/")

    db = get_db()

    questions = db.execute(
        "SELECT * FROM questions WHERE LOWER(subject)=LOWER(?) AND LOWER(type)=LOWER(?)",
        (subject, type)
    ).fetchall()

    if len(questions) == 0:
        return f"No questions found for {subject} - {type}"

    if "index" not in session:
        session["index"] = 0
        session["score"] = 0
        session["answers"] = []
        session["start_time"] = time.time()

    index = int(session.get("index", 0))

    if request.method == "POST":
        if index < len(questions):
            selected = request.form.get("answer")
            correct = questions[index]["correct"]

            session["answers"].append({
                "question": questions[index]["question"],
                "selected": selected,
                "correct": correct
            })

            if selected == correct:
                session["score"] += 1

        session["index"] = index + 1
        return redirect(f"/quiz/{subject}/{type}")

    if index >= len(questions):
        score = int(session.get("score", 0))
        total = len(questions)
        time_taken = int(time.time() - session.get("start_time", time.time()))

        db.execute(
            "INSERT INTO results (username, score, total, time_taken) VALUES (?,?,?,?)",
            (session["user"], score, total, time_taken)
        )
        db.commit()

        # Rank
        all_results = db.execute("""
        SELECT * FROM results
        ORDER BY score DESC, time_taken ASC
        """).fetchall()

        rank = 1
        for r in all_results:
            if r["username"] == session["user"] and r["score"] == score and r["time_taken"] == time_taken:
                break
            rank += 1

        session["final_answers"] = session.get("answers", [])
        session["time_taken"] = time_taken
        session["rank"] = rank

        session.pop("index", None)
        session.pop("score", None)
        session.pop("answers", None)
        session.pop("start_time", None)

        return redirect(f"/result?score={score}&total={total}")

    q = questions[index]
    progress = int((index / len(questions)) * 100)

    return render_template("quiz.html", question=q, progress=progress)

# ---------------- RESULT ----------------
@app.route("/result")
def result():
    score = int(request.args.get("score", 0))
    total = int(request.args.get("total", 0))

    return render_template("result.html",
        score=score,
        total=total,
        answers=session.get("final_answers", []),
        time_taken=session.get("time_taken", 0),
        rank=session.get("rank", 0)
    )

# ---------------- LEADERBOARD ----------------
@app.route("/leaderboard")
def leaderboard():
    if "user" not in session:
        return redirect("/")

    db = get_db()

    data = db.execute("""
    SELECT username, score, total, time_taken
    FROM results
    ORDER BY score DESC, time_taken ASC
    LIMIT 10
    """).fetchall()

    return render_template("leaderboard.html", data=data)

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    user = session.get("user")
    session.clear()
    return render_template("logout.html", user=user)

# ---------------- DEBUG ----------------
@app.route("/debug")
def debug():
    return "App is working!"

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
