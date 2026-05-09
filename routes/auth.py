"""
routes/auth.py — Xác thực người dùng
Endpoints: /api/login, /api/logout, /api/register, /api/change-password
"""
from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from database import get_db, hash_pw
from services.helpers import log_activity

auth_bp = Blueprint("auth", __name__)


# ── PAGES ─────────────────────────────────────────────────────────────────────

@auth_bp.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("login.html")


@auth_bp.route("/register")
def register_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("register.html")


# ── API ───────────────────────────────────────────────────────────────────────

@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.json
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=? AND is_active=1",
        (data["username"], hash_pw(data["password"]))
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "Sai tài khoản hoặc mật khẩu"}), 401

    session.update({
        "user_id":  user["id"],
        "username": user["username"],
        "role":     user["role"],
    })

    db = get_db()
    from datetime import datetime
    db.execute("UPDATE users SET last_login=? WHERE id=?",
               (datetime.now().isoformat(), user["id"]))
    db.commit()
    db.close()

    log_activity(user["id"], "LOGIN", "Đăng nhập thành công")
    return jsonify({"role": user["role"], "username": user["username"]})


@auth_bp.route("/api/logout", methods=["POST"])
def api_logout():
    if "user_id" in session:
        log_activity(session["user_id"], "LOGOUT", "Đăng xuất")
    session.clear()
    return jsonify({"ok": True})


@auth_bp.route("/api/register", methods=["POST"])
def api_register():
    data     = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Thiếu thông tin bắt buộc"}), 400
    if len(username) < 4:
        return jsonify({"error": "Tên đăng nhập phải có ít nhất 4 ký tự"}), 400
    if len(password) < 6:
        return jsonify({"error": "Mật khẩu phải có ít nhất 6 ký tự"}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username,email,password,role) VALUES (?,?,?,?)",
            (username, f"{username}@adsanalytics.local", hash_pw(password), "user")
        )
        conn.commit()
        log_activity(None, "REGISTER", f"User mới: {username}")
        return jsonify({"ok": True})
    except Exception:
        return jsonify({"error": "Tên đăng nhập đã tồn tại"}), 400
    finally:
        conn.close()


@auth_bp.route("/api/change-password", methods=["POST"])
def api_change_password():
    if "user_id" not in session:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    data       = request.json or {}
    current_pw = data.get("current_password", "")
    new_pw     = data.get("new_password", "")

    if not current_pw or not new_pw:
        return jsonify({"error": "Vui lòng điền đầy đủ thông tin"}), 400
    if len(new_pw) < 6:
        return jsonify({"error": "Mật khẩu mới phải có ít nhất 6 ký tự"}), 400

    uid  = session["user_id"]
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id=? AND password=?",
        (uid, hash_pw(current_pw))
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "Mật khẩu hiện tại không đúng"}), 401

    conn.execute("UPDATE users SET password=? WHERE id=?", (hash_pw(new_pw), uid))
    conn.commit()
    conn.close()

    log_activity(uid, "CHANGE_PASSWORD", "Đổi mật khẩu thành công")
    return jsonify({"ok": True, "message": "Đổi mật khẩu thành công"})