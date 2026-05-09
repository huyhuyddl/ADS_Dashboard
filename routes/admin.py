"""
routes/admin.py — Admin panel
Endpoints: /admin, /api/admin/*
"""
from functools import wraps
from datetime import datetime

from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template

from database import get_db, hash_pw
from services.helpers import log_activity
from services.data import get_all_data

admin_bp = Blueprint("admin", __name__)


def login_required(f):
    @wraps(f)
    def d(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("auth.login_page"))
        return f(*a, **kw)
    return d


def admin_required(f):
    @wraps(f)
    def d(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("auth.login_page"))
        if session.get("role") != "admin":
            return jsonify({"error": "Forbidden"}), 403
        return f(*a, **kw)
    return d


# ── PAGE ──────────────────────────────────────────────────────────────────────

@admin_bp.route("/admin")
@login_required
def admin_page():
    if session.get("role") != "admin":
        return redirect(url_for("dashboard.dashboard_page"))
    return render_template("admin.html", username=session["username"])


# ── API: USERS ────────────────────────────────────────────────────────────────

@admin_bp.route("/api/admin/users")
@admin_required
def api_admin_users():
    conn  = get_db()
    users = conn.execute(
        "SELECT id,username,email,role,is_active,created_at,last_login FROM users ORDER BY id"
    ).fetchall()
    result = []
    for u in users:
        ud        = dict(u)
        platforms = conn.execute(
            "SELECT platform,account_name,is_active,last_synced FROM platform_connections WHERE user_id=?",
            (u["id"],)
        ).fetchall()
        ud["platforms"] = [dict(p) for p in platforms]
        result.append(ud)
    conn.close()
    return jsonify(result)


@admin_bp.route("/api/admin/users", methods=["POST"])
@admin_required
def api_create_user():
    data = request.json
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username,email,password,role) VALUES (?,?,?,?)",
            (data["username"], data["email"],
             hash_pw(data["password"]), data.get("role", "user"))
        )
        conn.commit()
        log_activity(session["user_id"], "CREATE_USER", f'Tạo user {data["username"]}')
        return jsonify({"ok": True})
    except Exception:
        return jsonify({"error": "Username hoặc email đã tồn tại"}), 400
    finally:
        conn.close()


@admin_bp.route("/api/admin/users/<int:uid>/toggle", methods=["POST"])
@admin_required
def api_toggle_user(uid):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    new_status = 0 if user["is_active"] else 1
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (new_status, uid))
    conn.commit()
    conn.close()
    action = "Mở khóa" if new_status else "Khóa"
    log_activity(session["user_id"], "TOGGLE_USER", f'{action} user {user["username"]}')
    return jsonify({"is_active": new_status})


@admin_bp.route("/api/admin/users/<int:uid>/role", methods=["POST"])
@admin_required
def api_change_role(uid):
    role = request.json.get("role")
    if role not in ("admin", "user"):
        return jsonify({"error": "Invalid role"}), 400
    conn = get_db()
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
    conn.commit()
    conn.close()
    log_activity(session["user_id"], "CHANGE_ROLE", f"Đổi role user #{uid} → {role}")
    return jsonify({"ok": True})


# ── API: LOGS & STATS ─────────────────────────────────────────────────────────

@admin_bp.route("/api/admin/logs")
@admin_required
def api_admin_logs():
    uid  = request.args.get("user_id")
    conn = get_db()
    if uid:
        logs = conn.execute(
            """SELECT l.*,u.username FROM activity_logs l
               JOIN users u ON l.user_id=u.id
               WHERE l.user_id=? ORDER BY l.created_at DESC LIMIT 100""",
            (uid,)
        ).fetchall()
    else:
        logs = conn.execute(
            """SELECT l.*,u.username FROM activity_logs l
               JOIN users u ON l.user_id=u.id
               ORDER BY l.created_at DESC LIMIT 200"""
        ).fetchall()
    conn.close()
    return jsonify([dict(l) for l in logs])


@admin_bp.route("/api/admin/stats")
@admin_required
def api_admin_stats():
    conn   = get_db()
    total  = conn.execute('SELECT COUNT(*) as c FROM users WHERE role="user"').fetchone()["c"]
    active = conn.execute('SELECT COUNT(*) as c FROM users WHERE role="user" AND is_active=1').fetchone()["c"]
    today  = conn.execute(
        'SELECT COUNT(*) as c FROM activity_logs WHERE action="LOGIN" AND date(created_at)=date("now")'
    ).fetchone()["c"]
    conns  = conn.execute('SELECT COUNT(*) as c FROM platform_connections WHERE is_active=1').fetchone()["c"]
    conn.close()
    total_spend = sum(get_all_data(i, 30, force_mock=True)["total_spend"] for i in range(2, 5))
    return jsonify({
        "total_users":       total,
        "active_users":      active,
        "today_logins":      today,
        "total_connections": conns,
        "total_spend":       total_spend,
    })


@admin_bp.route("/api/admin/preview-dashboard")
@admin_required
def api_admin_preview_dashboard():
    uid  = request.args.get("user_id", type=int)
    days = int(request.args.get("days", 7))
    if not uid:
        return jsonify({"error": "Missing user_id"}), 400

    data = get_all_data(uid, days, force_mock=False)

    conn    = get_db()
    budgets = conn.execute(
        "SELECT platform,monthly_limit FROM budgets WHERE user_id=?", (uid,)
    ).fetchall()
    conn.close()

    data["budgets"] = {b["platform"]: b["monthly_limit"] for b in budgets}
    log_activity(session["user_id"], "VIEW_DASHBOARD", f"Admin preview user #{uid}")
    return jsonify(data)