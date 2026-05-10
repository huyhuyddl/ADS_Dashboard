
from flask import Flask, session, redirect, url_for
from config import SECRET_KEY
from database import init_db

# ── KHỞI TẠO APP ──────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = SECRET_KEY

# ── ĐĂNG KÝ BLUEPRINTS ────────────────────────────────────────────────────────
from routes.auth      import auth_bp
from routes.dashboard import dashboard_bp
from routes.platforms import platforms_bp
from routes.admin     import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(platforms_bp)
app.register_blueprint(admin_bp)


# ── INDEX REDIRECT ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))
    if session.get("role") == "admin":
        return redirect(url_for("admin.admin_page"))
    return redirect(url_for("dashboard.dashboard_page"))


# ── RUN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)