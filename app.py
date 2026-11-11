import os
import sqlite3
import secrets
import json
import ipaddress
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "lab.db"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
# Render sits behind one trusted reverse proxy; do not increase these counts casually.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 MB
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise RuntimeError("Configure ADMIN_PASSWORD antes de iniciar o servidor.")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                ip_address TEXT,
                country TEXT,
                region TEXT,
                city TEXT,
                latitude REAL,
                longitude REAL,
                geo_provider TEXT,
                user_agent TEXT,
                language TEXT,
                screen_size TEXT,
                consent_version TEXT NOT NULL,
                screenshot_name TEXT
            )
        """)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(visits)").fetchall()}
        for column, definition in (
            ("latitude", "REAL"),
            ("longitude", "REAL"),
            ("geo_provider", "TEXT"),
            ("country", "TEXT"),
            ("region", "TEXT"),
            ("city", "TEXT"),
        ):
            if column not in existing:
                conn.execute(f"ALTER TABLE visits ADD COLUMN {column} {definition}")

def lookup_ip_location(ip_text):
    """Approximate IP geolocation. Never requests device GPS or browser location."""
    try:
        ip_obj = ipaddress.ip_address(ip_text)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
            return {}
        req = Request(
            f"https://ipwho.is/{ip_text}",
            headers={"User-Agent": "CybersecurityErrorLab/1.0"}
        )
        with urlopen(req, timeout=4) as response:
            payload = json.loads(response.read(250_000).decode("utf-8"))
        if not payload.get("success"):
            return {}
        connection = payload.get("connection") or {}
        return {
            "country": str(payload.get("country") or "")[:100],
            "region": str(payload.get("region") or "")[:100],
            "city": str(payload.get("city") or "")[:100],
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "geo_provider": "ipwho.is"
        }
    except Exception:
        # A lookup failure must not prevent the consented technical visit record.
        return {}

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https://*.tile.openstreetmap.org; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    return response

@app.get("/health")
def health():
    return {"status": "ok"}, 200

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/api/visit")
def record_visit():
    data = request.get_json(silent=True) or {}
    if data.get("consent") is not True:
        return jsonify({"ok": False, "error": "Consentimento obrigatório."}), 400

    # Only the immediate peer address is used. Do not trust arbitrary X-Forwarded-For
    # headers unless you explicitly configure a trusted reverse proxy.
    ip = request.remote_addr or "indisponivel"
    user_agent = request.headers.get("User-Agent", "")[:500]
    language = request.headers.get("Accept-Language", "")[:200]
    screen_size = str(data.get("screen_size", ""))[:40]

    # IP-based geolocation is an approximate server-side lookup; no GPS/browser prompt.
    geo = lookup_ip_location(ip)
    with db() as conn:
        cur = conn.execute("""
            INSERT INTO visits
            (created_at, ip_address, country, region, city, latitude, longitude,
             geo_provider, user_agent, language, screen_size, consent_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            ip, geo.get("country"), geo.get("region"), geo.get("city"),
            geo.get("latitude"), geo.get("longitude"), geo.get("geo_provider"),
            user_agent, language, screen_size, "1.1"
        ))
        visit_id = cur.lastrowid

    session["last_visit_id"] = visit_id
    return jsonify({"ok": True, "visit_id": visit_id})

@app.post("/api/screenshot")
def upload_screenshot():
    if not session.get("last_visit_id"):
        return jsonify({"ok": False, "error": "Registre o acesso com consentimento primeiro."}), 400
    image = request.files.get("screenshot")
    if not image or image.mimetype not in ("image/png", "image/jpeg", "image/webp"):
        return jsonify({"ok": False, "error": "Envie PNG, JPEG ou WEBP."}), 400
    ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[image.mimetype]
    name = f"visit_{session['last_visit_id']}_{secrets.token_hex(6)}{ext}"
    image.save(os.path.join(UPLOAD_DIR, name))
    with db() as conn:
        conn.execute("UPDATE visits SET screenshot_name=? WHERE id=?", (name, session["last_visit_id"]))
    return jsonify({"ok": True})

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # ADMIN_PASSWORD is supplied as a deployment secret; compare directly.
        supplied = request.form.get("password", "")
        if secrets.compare_digest(supplied, ADMIN_PASSWORD):
            session.clear()
            session["admin"] = True
            return redirect(url_for("dashboard"))
        flash("Senha incorreta.")
    return render_template("login.html")

@app.post("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin")
@admin_required
def dashboard():
    with db() as conn:
        visits = conn.execute("SELECT * FROM visits ORDER BY id DESC LIMIT 300").fetchall()
        total = conn.execute("SELECT COUNT(*) AS n FROM visits").fetchone()["n"]
        screenshots = conn.execute("SELECT COUNT(*) AS n FROM visits WHERE screenshot_name IS NOT NULL").fetchone()["n"]
    map_points = [
        {"id": v["id"], "city": v["city"], "region": v["region"], "country": v["country"],
         "lat": v["latitude"], "lon": v["longitude"], "created_at": v["created_at"]}
        for v in visits if v["latitude"] is not None and v["longitude"] is not None
    ]
    return render_template("dashboard.html", visits=visits, total=total, screenshots=screenshots,
                           map_points=map_points)

@app.route("/admin/screenshot/<int:visit_id>")
@admin_required
def screenshot(visit_id):
    with db() as conn:
        row = conn.execute("SELECT screenshot_name FROM visits WHERE id=?", (visit_id,)).fetchone()
    if not row or not row["screenshot_name"]:
        return "Captura não encontrada.", 404
    path = os.path.join(UPLOAD_DIR, secure_filename(row["screenshot_name"]))
    if not os.path.isfile(path):
        return "Arquivo não encontrado.", 404
    return send_file(path)

@app.route("/admin/export.csv")
@admin_required
def export_csv():
    import csv
    from io import StringIO
    from flask import Response
    with db() as conn:
        rows = conn.execute("SELECT id, created_at, ip_address, country, region, city, latitude, longitude, geo_provider, user_agent, language, screen_size, consent_version, screenshot_name FROM visits ORDER BY id DESC").fetchall()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "created_at", "ip_address", "country", "region", "city", "latitude", "longitude", "geo_provider", "user_agent", "language", "screen_size", "consent_version", "screenshot_name"])
    for row in rows:
        writer.writerow(list(row))
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=cybersecurity_error_lab.csv"})

@app.route("/admin/delete-all", methods=["POST"])
@admin_required
def delete_all():
    with db() as conn:
        rows = conn.execute("SELECT screenshot_name FROM visits WHERE screenshot_name IS NOT NULL").fetchall()
        conn.execute("DELETE FROM visits")
    for row in rows:
        if row["screenshot_name"]:
            path = os.path.join(UPLOAD_DIR, secure_filename(row["screenshot_name"]))
            if os.path.isfile(path):
                os.remove(path)
    flash("Registros e capturas apagados.")
    return redirect(url_for("dashboard"))

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
