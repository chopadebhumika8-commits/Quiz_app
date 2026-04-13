from flask import Flask, render_template, request, redirect, session
import sqlite3
import time
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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

init_db()

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

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
            session.clear()  # clean previous session
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
    return render_template("dashboard.html")

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

    # INIT
    if "index" not in session:
        session["index"] = 0
        session["score"] = 0
        session["answers"] = []
        session["start_time"] = time.time()

    index = int(session.get("index", 0))

    # SUBMIT
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

    # FINISH
    if index >= len(questions):
        score = int(session.get("score", 0))
        total = len(questions)

        end_time = time.time()
        time_taken = int(end_time - session.get("start_time", end_time))

        db.execute(
            "INSERT INTO results (username, score, total, time_taken) VALUES (?,?,?,?)",
            (session["user"], score, total, time_taken)
        )
        db.commit()

        # RANK (CORRECT)
        all_results = db.execute("""
        SELECT * FROM results
        ORDER BY score DESC, time_taken ASC
        """).fetchall()

        rank = 1
        for r in all_results:
            if r["username"] == session["user"] and r["score"] == score and r["time_taken"] == time_taken:
                break
            rank += 1

        # SAVE DATA
        session["final_answers"] = session.get("answers", [])
        session["time_taken"] = time_taken
        session["rank"] = rank

        # CLEAR QUIZ SESSION ONLY
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

# ---------------- ADMIN ----------------
@app.route("/admin", methods=["GET","POST"])
def admin():
    db = get_db()

    if request.method == "POST":
        subject = request.form.get("subject")
        type = request.form.get("type")
        q = request.form.get("question")
        o1 = request.form.get("o1")
        o2 = request.form.get("o2")
        o3 = request.form.get("o3")
        o4 = request.form.get("o4")
        correct = request.form.get("correct")

        db.execute("""
        INSERT INTO questions
        (subject,type,question,option1,option2,option3,option4,correct)
        VALUES (?,?,?,?,?,?,?,?)
        """, (subject,type,q,o1,o2,o3,o4,correct))

        db.commit()

    questions = db.execute("SELECT * FROM questions").fetchall()
    return render_template("admin.html", questions=questions)

# ---------------- DELETE ----------------
@app.route("/delete/<int:id>")
def delete(id):
    db = get_db()
    db.execute("DELETE FROM questions WHERE id=?", (id,))
    db.commit()
    return redirect("/admin")

# ---------------- EDIT ----------------
@app.route("/edit/<int:id>", methods=["GET","POST"])
def edit(id):
    db = get_db()

    if request.method == "POST":
        q = request.form.get("question")
        o1 = request.form.get("o1")
        o2 = request.form.get("o2")
        o3 = request.form.get("o3")
        o4 = request.form.get("o4")
        correct = request.form.get("correct")

        db.execute("""
        UPDATE questions SET
        question=?, option1=?, option2=?, option3=?, option4=?, correct=?
        WHERE id=?
        """, (q,o1,o2,o3,o4,correct,id))

        db.commit()
        return redirect("/admin")

    question = db.execute("SELECT * FROM questions WHERE id=?", (id,)).fetchone()
    return render_template("edit.html", q=question)

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
    total_score = sum([h["score"] for h in history])
    total_marks = sum([h["total"] for h in history])

    percentage = int((total_score / total_marks) * 100) if total_marks > 0 else 0

    return render_template("profile.html",
        username=session["user"],
        history=history,
        total_quiz=total_quiz,
        percentage=percentage
    )

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    user = session.get("user")
    session.clear()
    return render_template("logout.html", user=user)

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
    LIMIT 10
    """).fetchall()

    return render_template("leaderboard.html", users=users)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
