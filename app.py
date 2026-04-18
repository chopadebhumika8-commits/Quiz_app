from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3, time, os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

DB_PATH = os.path.join(os.getcwd(), "database.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def create_tables():
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
    db.execute("""CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT,type TEXT,question TEXT,
        option1 TEXT,option2 TEXT,option3 TEXT,option4 TEXT,correct TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,score INTEGER,total INTEGER,time_taken INTEGER)""")
    db.commit()

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
            return redirect(url_for("dashboard"))

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
        (subject, type)).fetchall()

    if not questions:
        return "No questions"

    if "index" not in session:
        session["index"] = 0
        session["score"] = 0
        session["answers"] = []
        session["start_time"] = time.time()

    i = session["index"]

    if request.method == "POST":
        selected = request.form.get("answer")
        correct = questions[i]["correct"]

        session["answers"].append({
            "question": questions[i]["question"],
            "selected": selected,
            "correct": correct
        })

        if selected == correct:
            session["score"] += 1

        session["index"] += 1
        return redirect(url_for("quiz", subject=subject, type=type))

    if i >= len(questions):
        score = session["score"]
        total = len(questions)
        time_taken = int(time.time() - session["start_time"])

        db.execute("INSERT INTO results (username,score,total,time_taken) VALUES (?,?,?,?)",
                   (session["user"], score, total, time_taken))
        db.commit()

        # RANK CALCULATION
        results = db.execute("SELECT * FROM results ORDER BY score DESC, time_taken ASC").fetchall()
        rank = 1
        for r in results:
            if r["username"] == session["user"] and r["score"] == score:
                break
            rank += 1

        session["rank"] = rank
        session["time_taken"] = time_taken
        session["final_answers"] = session["answers"]

        session.pop("index")
        session.pop("score")
        session.pop("answers")
        session.pop("start_time")

        return redirect(url_for("result", score=score, total=total))

    return render_template("quiz.html", question=questions[i])

# ---------------- RESULT ----------------
@app.route("/result")
def result():
    return render_template("result.html",
        score=int(request.args.get("score", 0)),
        total=int(request.args.get("total", 0)),
        answers=session.get("final_answers", []),
        time_taken=session.get("time_taken", 0)
    )

# ---------------- LEADERBOARD ----------------
@app.route("/leaderboard")
def leaderboard():
    db = get_db()
    users = db.execute("""
    SELECT username, score, total, time_taken
    FROM results
    ORDER BY score DESC, time_taken ASC
    LIMIT 10
    """).fetchall()

    return render_template("leaderboard.html", users=users)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
