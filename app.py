from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import time
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- ADMIN ----------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# ---------------- DATABASE ----------------
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- INIT DB ----------------
def init_db():
    with sqlite3.connect(DB_PATH) as db:
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
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            score INTEGER,
            total INTEGER,
            time_taken INTEGER
        )""")
        db.commit()

init_db()

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

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        db = get_db()
        try:
            db.execute("INSERT INTO users VALUES (?,?)", (u, generate_password_hash(p)))
            db.commit()
            return redirect("/")
        except:
            return "User already exists"

    return render_template("signup.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html")

# ---------------- PROFILE ----------------
@app.route("/profile")
def profile():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    history = db.execute("SELECT score,total FROM results WHERE username=?", (session["user"],)).fetchall()

    return render_template("profile.html", user=session["user"], history=history)

# ---------------- QUIZ ----------------
@app.route("/quiz/<subject>/<type>", methods=["GET", "POST"])
def quiz(subject, type):
    if "user" not in session:
        return redirect("/")

    db = get_db()
    questions = db.execute(
        "SELECT * FROM questions WHERE LOWER(subject)=LOWER(?) AND LOWER(type)=LOWER(?)",
        (subject, type)
    ).fetchall()

    if not questions:
        return "No Questions Found"

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
        return redirect(request.url)

    if i >= len(questions):
        score = session["score"]
        total = len(questions)
        time_taken = int(time.time() - session["start_time"])

        db.execute(
            "INSERT INTO results (username, score, total, time_taken) VALUES (?,?,?,?)",
            (session["user"], score, total, time_taken)
        )
        db.commit()

        session["final_answers"] = session["answers"]
        session["time_taken"] = time_taken
        session["last_score"] = score
        session["last_total"] = total

        session.pop("index", None)
        session.pop("score", None)
        session.pop("answers", None)
        session.pop("start_time", None)

        return redirect(url_for("result", score=score, total=total))

    return render_template("quiz.html",
                           question=questions[i],
                           progress=int((i / len(questions)) * 100))

# ---------------- RESULT ----------------
@app.route("/result")
def result():
    return render_template("result.html",
        score=request.args.get("score", 0),
        total=request.args.get("total", 0),
        answers=session.get("final_answers", []),
        time_taken=session.get("time_taken", 0)
    )

# ---------------- CERTIFICATE ----------------
@app.route("/certificate")
def certificate():
    if "user" not in session:
        return redirect("/")

    return render_template("certificate.html",
        user=session.get("user"),
        score=session.get("last_score", 0),
        total=session.get("last_total", 0)
    )

# ---------------- LEADERBOARD ----------------
@app.route("/leaderboard")
def leaderboard():
    db = get_db()
    users = db.execute("""
    SELECT username, MAX(score) as best_score
    FROM results
    GROUP BY username
    ORDER BY best_score DESC
    """).fetchall()

    return render_template("leaderboard.html", users=users)

# ---------------- ADMIN ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    # LOGIN CHECK
    if not session.get("admin"):
        if request.method == "POST":
            key = request.form.get("key")
            if key == ADMIN_PASSWORD:
                session["admin"] = True
                return redirect("/admin")

        return """
        <h2>Admin Login</h2>
        <form method="POST">
            <input name="key" placeholder="Enter Admin Password">
            <button>Login</button>
        </form>
        """

    db = get_db()

    # ADD QUESTION
    if request.method == "POST" and "question" in request.form:
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
    if not session.get("admin"):
        return redirect("/admin")

    db = get_db()
    db.execute("DELETE FROM questions WHERE id=?", (id,))
    db.commit()
    return redirect("/admin")

# ---------------- EDIT ----------------
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if not session.get("admin"):
        return redirect("/admin")

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
    return redirect("/admin")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
