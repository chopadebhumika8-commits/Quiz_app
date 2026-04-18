from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3, time

app = Flask(__name__)
app.secret_key = "secret123"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

DB = "database.db"

def get_db():
    conn = sqlite3.connect(DB)
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

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()

        if user and user["password"] == p:
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
        "SELECT * FROM questions WHERE LOWER(subject)=LOWER(?) AND LOWER(type)=LOWER(?)",
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
        return redirect(url_for("quiz", subject=subject, type=type))

    if index >= len(questions):
        score = session["score"]
        total = len(questions)
        time_taken = int(time.time() - session["start_time"])

        db.execute(
            "INSERT INTO results (username, score, total, time_taken) VALUES (?,?,?,?)",
            (session["user"], score, total, time_taken)
        )
        db.commit()

        # ---------------- RANK CALCULATION ----------------
        all_results = db.execute("""
            SELECT * FROM results
            ORDER BY score DESC, time_taken ASC
        """).fetchall()

        rank = 1
        for r in all_results:
            if r["username"] == session["user"] and r["score"] == score and r["time_taken"] == time_taken:
                break
            rank += 1

        # SAVE FOR RESULT PAGE
        session["rank"] = rank
        session["time_taken"] = time_taken
        session["final_answers"] = session["answers"]
        session["last_score"] = score
        session["last_total"] = total

        # CLEAR QUIZ SESSION
        session.pop("index")
        session.pop("score")
        session.pop("answers")
        session.pop("start_time")

        return redirect(url_for("result", score=score, total=total))

    q = questions[index]
    progress = int((index / len(questions)) * 100)

    return render_template("quiz.html", question=q, progress=progress)

# ---------------- RESULT ----------------
@app.route("/result")
def result():
    return render_template("result.html",
        score=int(request.args.get("score", 0)),
        total=int(request.args.get("total", 0)),
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
    users = db.execute("""
        SELECT username, score, total, time_taken
        FROM results
        ORDER BY score DESC, time_taken ASC
        LIMIT 10
    """).fetchall()

    return render_template("leaderboard.html", users=users)

# ---------------- CERTIFICATE ----------------
@app.route("/certificate")
def certificate():
    if "user" not in session:
        return redirect("/")

    return render_template("certificate.html",
        user=session.get("user"),
        score=session.get("last_score", 0),
        total=session.get("last_total", 0),
        rank=session.get("rank", 0)
    )

# ---------------- ADMIN LOGIN ----------------
@app.route("/admin_login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin"))

        return render_template("admin_login.html", error="Invalid Login")

    return render_template("admin_login.html")

# ---------------- ADMIN PANEL ----------------
@app.route("/admin", methods=["GET","POST"])
def admin():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

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

# ---------------- EDIT ----------------
@app.route("/edit/<int:id>", methods=["GET","POST"])
def edit(id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

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
        return redirect(url_for("admin"))

    q = db.execute("SELECT * FROM questions WHERE id=?", (id,)).fetchone()
    return render_template("edit.html", q=q)

# ---------------- DELETE ----------------
@app.route("/delete/<int:id>")
def delete(id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    db = get_db()
    db.execute("DELETE FROM questions WHERE id=?", (id,))
    db.commit()
    return redirect(url_for("admin"))

# ---------------- LOGOUT ----------------
@app.route("/admin_logout")
def admin_logout():
    session.clear()
    return render_template("admin_logout.html")   # shows logout page

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
