import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-development-secret"),
    DATABASE=os.environ.get("DATABASE_PATH", os.path.join(app.instance_path, "documents.db")),
    TESTING=False,
)
os.makedirs(app.instance_path, exist_ok=True)

def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE"])), exist_ok=True)
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        document_type TEXT NOT NULL,
        expiry_date TEXT NOT NULL,
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_documents_user_expiry
        ON documents(user_id, expiry_date);
    CREATE INDEX IF NOT EXISTS idx_documents_user_title
        ON documents(user_id, title);
    """)
    db.commit()

def expiry_status(expiry_date, today=None):
    """Return Expired, Expiring Soon (0-30 days), or Valid."""
    try:
        expiry = date.fromisoformat(str(expiry_date))
    except (TypeError, ValueError):
        raise ValueError("Expiry date must use YYYY-MM-DD format")
    today = today or date.today()
    days_left = (expiry - today).days
    if days_left < 0:
        return "Expired"
    if days_left <= 30:
        return "Expiring Soon"
    return "Valid"

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def valid_document(data):
    title = (data.get("title") or "").strip()
    doc_type = (data.get("document_type") or "").strip()
    expiry = (data.get("expiry_date") or "").strip()
    notes = (data.get("notes") or "").strip()
    if not title or not doc_type or not expiry:
        return None, "Title, document type and expiry date are required"
    try:
        date.fromisoformat(expiry)
    except ValueError:
        return None, "Expiry date must use YYYY-MM-DD format"
    return {"title": title, "document_type": doc_type, "expiry_date": expiry, "notes": notes}, None

@app.before_request
def ensure_database():
    if not app.config.get("TESTING"):
        init_db()

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if len(username) < 3 or len(password) < 6:
            flash("Username must be at least 3 characters and password at least 6 characters.", "error")
            return render_template("register.html")
        db = get_db()
        try:
            db.execute("INSERT INTO users(username, password_hash) VALUES (?, ?)",
                       (username, generate_password_hash(password)))
            db.commit()
        except sqlite3.IntegrityError:
            flash("That username is already registered.", "error")
            return render_template("register.html")
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = get_db().execute("SELECT id, password_hash FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = username
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    rows = get_db().execute(
        "SELECT id, title, document_type, expiry_date, notes FROM documents "
        "WHERE user_id=? ORDER BY expiry_date ASC", (session["user_id"],)
    ).fetchall()
    docs = []
    for row in rows:
        item = dict(row)
        item["status"] = expiry_status(item["expiry_date"])
        docs.append(item)
    counts = {key: sum(d["status"] == key for d in docs) for key in ("Expired", "Expiring Soon", "Valid")}
    return render_template("dashboard.html", documents=docs, counts=counts)

@app.route("/documents/add", methods=["GET", "POST"])
@login_required
def add_document():
    if request.method == "POST":
        data, error = valid_document(request.form)
        if error:
            flash(error, "error")
        else:
            db = get_db()
            db.execute("INSERT INTO documents(user_id,title,document_type,expiry_date,notes) VALUES(?,?,?,?,?)",
                       (session["user_id"], data["title"], data["document_type"], data["expiry_date"], data["notes"]))
            db.commit()
            flash("Document added.", "success")
            return redirect(url_for("dashboard"))
    return render_template("document_form.html", document=None)

@app.route("/documents/<int:doc_id>/edit", methods=["GET", "POST"])
@login_required
def edit_document(doc_id):
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id=? AND user_id=?", (doc_id, session["user_id"])).fetchone()
    if not doc:
        return render_template("404.html"), 404
    if request.method == "POST":
        data, error = valid_document(request.form)
        if error:
            flash(error, "error")
        else:
            db.execute("UPDATE documents SET title=?,document_type=?,expiry_date=?,notes=? WHERE id=? AND user_id=?",
                       (data["title"], data["document_type"], data["expiry_date"], data["notes"], doc_id, session["user_id"]))
            db.commit()
            flash("Document updated.", "success")
            return redirect(url_for("dashboard"))
    return render_template("document_form.html", document=doc)

@app.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    db = get_db()
    db.execute("DELETE FROM documents WHERE id=? AND user_id=?", (doc_id, session["user_id"]))
    db.commit()
    flash("Document deleted if it belonged to your account.", "success")
    return redirect(url_for("dashboard"))

@app.route("/api/documents", methods=["GET", "POST"])
@login_required
def api_documents():
    db = get_db()
    if request.method == "GET":
        rows = db.execute("SELECT id,title,document_type,expiry_date,notes FROM documents WHERE user_id=? ORDER BY expiry_date",
                          (session["user_id"],)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["status"] = expiry_status(item["expiry_date"])
            result.append(item)
        return jsonify(result)
    data, error = valid_document(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400
    cur = db.execute("INSERT INTO documents(user_id,title,document_type,expiry_date,notes) VALUES(?,?,?,?,?)",
                     (session["user_id"], data["title"], data["document_type"], data["expiry_date"], data["notes"]))
    db.commit()
    return jsonify({"id": cur.lastrowid, **data, "status": expiry_status(data["expiry_date"])}), 201

@app.route("/api/documents/<int:doc_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_document_detail(doc_id):
    db = get_db()
    row = db.execute("SELECT id,title,document_type,expiry_date,notes FROM documents WHERE id=? AND user_id=?",
                     (doc_id, session["user_id"])).fetchone()
    if request.method == "GET":
        if not row:
            return jsonify({"error": "Document not found"}), 404
        item = dict(row)
        item["status"] = expiry_status(item["expiry_date"])
        return jsonify(item)
    if request.method == "PUT":
        if not row:
            return jsonify({"error": "Document not found"}), 404
        data, error = valid_document(request.get_json(silent=True) or {})
        if error:
            return jsonify({"error": error}), 400
        db.execute("UPDATE documents SET title=?,document_type=?,expiry_date=?,notes=? WHERE id=? AND user_id=?",
                   (data["title"], data["document_type"], data["expiry_date"], data["notes"], doc_id, session["user_id"]))
        db.commit()
        return jsonify({"id": doc_id, **data, "status": expiry_status(data["expiry_date"])})
    if not row:
        return jsonify({"error": "Document not found"}), 404
    db.execute("DELETE FROM documents WHERE id=? AND user_id=?", (doc_id, session["user_id"]))
    db.commit()
    return jsonify({"message": "Document deleted"})

@app.route("/api/expiry-status/<string:expiry>")
@login_required
def api_expiry_status(expiry):
    try:
        return jsonify({"expiry_date": expiry, "status": expiry_status(expiry)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
