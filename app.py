import json
import os
import re
import secrets
import sqlite3
import urllib.error
import urllib.request
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

APP_NAME = "AuraAI"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("OLLAMA_DEFAULT_MODEL", "qwen2.5:3b")
DEFAULT_SYSTEM_PROMPT = (
    "Sei Aura AI, un'intelligenza artificiale personale che gira interamente in locale "
    "sul computer dell'utente. Sei veloce, precisa, disponibile e rispondi in italiano."
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("AURAAI_DB_PATH", str(BASE_DIR / "auraai_local.db")))
USERS_JSON_PATH = Path(os.environ.get("AURAAI_USERS_JSON", str(BASE_DIR / "users.json")))

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_suspended INTEGER NOT NULL DEFAULT 0,
            suspension_reason TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            reason TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    db.commit()
    db.close()


def sync_users_json(conn=None):
    close_after = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        close_after = True

    try:
        rows = conn.execute(
            """
            SELECT id, username, password_hash, role, is_suspended, suspension_reason, created_at
            FROM users
            ORDER BY id ASC
            """
        ).fetchall()
        data = [dict(r) for r in rows]
        tmp_path = USERS_JSON_PATH.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, USERS_JSON_PATH)
    finally:
        if close_after:
            conn.close()


def restore_users_from_json(conn):
    if not USERS_JSON_PATH.exists():
        return
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        return
    try:
        raw = json.loads(USERS_JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(raw, list):
        return

    for item in raw:
        username = (item.get("username") or "").strip()
        pw_hash = item.get("password_hash") or ""
        if not username or not pw_hash:
            continue
        role = item.get("role") if item.get("role") in ("user", "owner") else "user"
        is_suspended = 1 if item.get("is_suspended") else 0
        reason = item.get("suspension_reason") or ""
        conn.execute(
            """
            INSERT OR IGNORE INTO users (username, password_hash, role, is_suspended, suspension_reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, pw_hash, role, is_suspended, reason),
        )
    conn.commit()


def bootstrap_persistence():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        restore_users_from_json(conn)
        sync_users_json(conn)
    finally:
        conn.close()


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        session.clear()
        return None
    return dict(row)


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Autenticazione richiesta"}), 401
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


def ollama_chat(messages, model=DEFAULT_MODEL, temperature=0.7, system_prompt=DEFAULT_SYSTEM_PROMPT):
    url = f"{OLLAMA_BASE_URL}/api/chat"
    final_messages = []
    if system_prompt:
        final_messages.append({"role": "system", "content": system_prompt})
    final_messages.extend(messages)

    payload = json.dumps(
        {
            "model": model or DEFAULT_MODEL,
            "messages": final_messages,
            "stream": False,
            "options": {"temperature": float(temperature)},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return ((data.get("message") or {}).get("content") or "").strip()


@app.route("/")
def index():
    if get_current_user():
        return redirect(url_for("chat"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if get_current_user():
            return redirect(url_for("chat"))
        return render_template("login.html")

    data = request.get_json(silent=True) or request.form or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Inserisci username e password."}), 400

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Credenziali non valide."}), 401

    session.clear()
    session["user_id"] = row["id"]
    dest = url_for("rules") if row["is_suspended"] else url_for("chat")
    return jsonify({"ok": True, "message": "Accesso riuscito.", "redirect": dest})


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or request.form or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if len(username) < 2:
        return jsonify({"error": "Lo username deve avere almeno 2 caratteri."}), 400
    if len(password) < 4:
        return jsonify({"error": "La password deve avere almeno 4 caratteri."}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        return jsonify({"error": "Questo username esiste già."}), 409

    total_users = db.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()[0]
    role = "owner" if total_users == 0 else "user"

    pw_hash = generate_password_hash(password)
    cursor = db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, pw_hash, role),
    )
    db.commit()
    sync_users_json(db)

    session.clear()
    session["user_id"] = cursor.lastrowid
    return (
        jsonify(
            {
                "ok": True,
                "message": "Account creato. Lettura regole...",
                "redirect": url_for("rules"),
            }
        ),
        201,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/rules")
@login_required
def rules():
    user = get_current_user()
    return render_template("rules.html", user=user)


@app.route("/anteprima_sospensione")
@login_required
def anteprima_sospensione():
    user = get_current_user()
    return render_template("rules.html", user=user)


@app.route("/chat")
@login_required
def chat():
    user = get_current_user()
    if user.get("is_suspended"):
        return render_template("rules.html", user=user), 403
    return render_template("chat.html", user=user)


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    user = get_current_user()
    if user.get("is_suspended"):
        return jsonify({"suspended": True, "reply": "Account sospeso."}), 403

    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"error": "Messaggio vuoto."}), 400

    model = (data.get("model") or DEFAULT_MODEL).strip()
    temperature = data.get("temperature", 0.7)
    system_prompt = (data.get("system") or DEFAULT_SYSTEM_PROMPT).strip()

    try:
        reply = ollama_chat(
            [{"role": "user", "content": msg}],
            model=model,
            temperature=temperature,
            system_prompt=system_prompt,
        )
        if not reply:
            reply = "Nessuna risposta ricevuta dal modello."
        return jsonify({"reply": reply})
    except urllib.error.URLError:
        return jsonify(
            {
                "reply": f"Ollama non raggiungibile su {OLLAMA_BASE_URL}. Avvia Ollama e assicurati che '{model}' sia installato."
            }
        )
    except Exception as exc:
        return jsonify({"reply": f"Errore durante la risposta: {exc}"})


@app.route("/api/change_password", methods=["POST"])
@login_required
def api_change_password():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    old_pass = data.get("old_password") or ""
    new_pass = data.get("new_password") or ""

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    if not row or not check_password_hash(row["password_hash"], old_pass):
        return jsonify({"success": False, "message": "Password attuale errata."})

    if (
        len(new_pass) < 8
        or not re.search(r"[A-Z]", new_pass)
        or not re.search(r"[0-9]", new_pass)
    ):
        return jsonify(
            {
                "success": False,
                "message": "La nuova password deve avere almeno 8 caratteri, 1 maiuscola e 1 numero.",
            }
        )

    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_pass), user["id"]),
    )
    db.commit()
    sync_users_json(db)
    return jsonify({"success": True, "message": "Password aggiornata."})


@app.route("/api/owner/search_user")
@login_required
def api_owner_search_user():
    user = get_current_user()
    if user.get("role") != "owner":
        return jsonify({"found": False}), 403
    username = (request.args.get("username") or "").strip()
    row = get_db().execute(
        "SELECT id, username, role, is_suspended, suspension_reason FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if not row:
        return jsonify({"found": False})
    return jsonify({"found": True, "user": dict(row)})


@app.route("/api/owner/suspend", methods=["POST"])
@login_required
def api_owner_suspend():
    user = get_current_user()
    if user.get("role") != "owner":
        return jsonify({"message": "Non autorizzato."}), 403
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    suspend = bool(data.get("suspend"))
    reason = (data.get("reason") or "").strip()

    db = get_db()
    target = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not target:
        return jsonify({"message": "Utente non trovato."})
    if target["role"] == "owner":
        return jsonify({"message": "Non puoi sospendere un Owner."})

    db.execute(
        "UPDATE users SET is_suspended = ?, suspension_reason = ? WHERE id = ?",
        (1 if suspend else 0, reason if suspend else "", target["id"]),
    )
    db.commit()
    sync_users_json(db)
    return jsonify({"message": "Stato utente aggiornato."})


@app.route("/api/owner/reports")
@login_required
def api_owner_reports():
    user = get_current_user()
    if user.get("role") != "owner":
        return jsonify({"reports": []}), 403
    rows = get_db().execute(
        "SELECT username, reason, message, timestamp FROM reports ORDER BY id DESC LIMIT 50"
    ).fetchall()
    return jsonify({"reports": [dict(r) for r in rows]})


bootstrap_persistence()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
