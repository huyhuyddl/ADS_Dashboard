"""
routes/dashboard.py — Dashboard page và API data
Endpoints: /dashboard, /api/dashboard-data, /api/connections/status,
           /api/budget/*, /api/history
"""
from datetime import datetime
from functools import wraps

from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template

from config import FB_APP_ID, FB_APP_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from config import TIKTOK_APP_ID, TIKTOK_APP_SECRET
from database import get_db
from services.helpers import get_connections, token_expired, log_activity
from services.data import get_platform_data, get_all_data

dashboard_bp = Blueprint("dashboard", __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


# ── PAGES ─────────────────────────────────────────────────────────────────────

@dashboard_bp.route("/dashboard")
@login_required
def dashboard_page():
    return render_template("dashboard.html",
                           username=session["username"],
                           role=session["role"])


# ── API: CONNECTIONS ──────────────────────────────────────────────────────────

@dashboard_bp.route("/api/connections/status")
@login_required
def api_connections_status():
    connections = get_connections(session["user_id"])
    can_connect = {
        "facebook": bool(FB_APP_ID and FB_APP_SECRET),
        "google":   bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "tiktok":   bool(TIKTOK_APP_ID and TIKTOK_APP_SECRET),
    }
    result = {}
    for p in ["facebook", "google", "tiktok"]:
        if p in connections:
            row       = connections[p]
            days_left = None
            if row.get("expires_at"):
                try:
                    exp_dt    = datetime.fromisoformat(row["expires_at"])
                    days_left = max(0, (exp_dt - datetime.now()).days)
                except Exception:
                    pass
            result[p] = {
                "connected":    True,
                "can_connect":  can_connect[p],
                "account_name": row.get("account_name", ""),
                "account_id":   row.get("account_id", ""),
                "days_left":    days_left,
                "needs_reauth": token_expired(row),
                "last_synced":  row.get("last_synced"),
            }
        else:
            result[p] = {"connected": False, "can_connect": can_connect[p]}
    return jsonify(result)


# ── API: DASHBOARD DATA ───────────────────────────────────────────────────────

@dashboard_bp.route("/api/dashboard-data")
@login_required
def api_dashboard_data():
    days       = int(request.args.get("days", 7))
    platform   = request.args.get("platform", "all")
    force_mock = request.args.get("force_mock", "0") == "1"
    uid        = session["user_id"]

    conn = get_db()
    budgets = {
        b["platform"]: b["monthly_limit"]
        for b in conn.execute(
            "SELECT platform, monthly_limit FROM budgets WHERE user_id=?", (uid,)
        ).fetchall()
    }
    conn.close()

    connections = get_connections(uid)

    if platform == "all":
        data = get_all_data(uid, days, force_mock)
    elif platform in ("facebook", "google", "tiktok"):
        pd = get_platform_data(uid, platform, days, force_mock)
        data = {
            "source":        "mock" if pd["is_mock"] else "api",
            "labels":        pd["labels"],
            "spend_series":  {platform: pd["spend_series"]},
            "total_spend":   pd["total_spend"],
            "total_revenue": pd["total_revenue"],
            "roas":          pd["roas"],
            "roi":           pd["roi"],
            "cpa":           pd["cpa"],
            "channel_stats": {
                platform: {
                    "spend":        pd["total_spend"],
                    "revenue":      pd["total_revenue"],
                    "roas":         pd["roas"],
                    "roi":          pd["roi"],
                    "cpa":          pd["cpa"],
                    "clicks":       pd["clicks"],
                    "impressions":  pd["impressions"],
                    "ctr":          pd["ctr"],
                    "is_mock":      pd["is_mock"],
                    "is_connected": pd["is_connected"],
                }
            },
            "connected_count": len(connections),
        }
    else:
        return jsonify({"error": "Invalid platform"}), 400

    data["budgets"]     = budgets
    data["no_ads_data"] = len(connections) == 0
    log_activity(uid, "VIEW_DASHBOARD", f"platform={platform} days={days}")
    return jsonify(data)


# ── API: BUDGET ───────────────────────────────────────────────────────────────

@dashboard_bp.route("/api/budget", methods=["GET"])
@login_required
def api_get_budget():
    uid      = session["user_id"]
    platform = request.args.get("platform", "all")
    conn     = get_db()
    if platform == "all":
        rows = conn.execute(
            "SELECT * FROM budget_settings WHERE user_id=?", (uid,)
        ).fetchall()
        conn.close()
        return jsonify({r["platform"]: dict(r) for r in rows})
    else:
        row = conn.execute(
            "SELECT * FROM budget_settings WHERE user_id=? AND platform=?",
            (uid, platform)
        ).fetchone()
        conn.close()
        return jsonify(dict(row) if row else {})


@dashboard_bp.route("/api/budget", methods=["POST"])
@login_required
def api_set_budget():
    uid  = session["user_id"]
    data = request.json

    platform     = data.get("platform")
    budget_limit = data.get("budget_limit")
    start_date   = data.get("start_date")
    end_date     = data.get("end_date")

    if not all([platform, budget_limit, start_date, end_date]):
        return jsonify({"error": "Thiếu thông tin"}), 400
    if platform not in ("facebook", "google", "tiktok"):
        return jsonify({"error": "Platform không hợp lệ"}), 400
    try:
        budget_limit = float(budget_limit)
        if budget_limit <= 0:
            return jsonify({"error": "Ngân sách phải lớn hơn 0"}), 400
    except Exception:
        return jsonify({"error": "Ngân sách không hợp lệ"}), 400

    conn = get_db()
    conn.execute("""
        INSERT INTO budget_settings
            (user_id,platform,budget_limit,start_date,end_date,alert_sent,updated_at)
        VALUES (?,?,?,?,?,0,datetime('now'))
        ON CONFLICT(user_id,platform) DO UPDATE SET
            budget_limit=excluded.budget_limit,
            start_date=excluded.start_date,
            end_date=excluded.end_date,
            alert_sent=0,
            updated_at=datetime('now')
    """, (uid, platform, budget_limit, start_date, end_date))
    conn.commit()
    conn.close()
    log_activity(uid, "SET_BUDGET",
                 f"{platform}: {budget_limit:,.0f}đ ({start_date} → {end_date})")
    return jsonify({"ok": True})


@dashboard_bp.route("/api/budget/<platform>", methods=["DELETE"])
@login_required
def api_delete_budget(platform):
    uid = session["user_id"]
    conn = get_db()
    conn.execute("DELETE FROM budget_settings WHERE user_id=? AND platform=?",
                 (uid, platform))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@dashboard_bp.route("/api/budget/check")
@login_required
def api_check_budget():
    uid  = session["user_id"]
    conn = get_db()
    budgets = conn.execute(
        "SELECT * FROM budget_settings WHERE user_id=?", (uid,)
    ).fetchall()
    conn.close()

    alerts = []
    today  = datetime.now()

    for b in budgets:
        b = dict(b)
        try:
            start = datetime.strptime(b["start_date"], "%Y-%m-%d")
            end   = datetime.strptime(b["end_date"],   "%Y-%m-%d")
        except Exception:
            continue

        if today < start or today > end:
            continue

        days_elapsed = max(1, (today - start).days + 1)
        pd    = get_platform_data(uid, b["platform"], days_elapsed)

        # Bỏ qua nếu là mock data
        if pd.get("source") == "mock":
            continue

        spend = pd.get("total_spend", 0)
        pct   = round(spend / b["budget_limit"] * 100, 1) if b["budget_limit"] else 0

        item = {
            "platform":     b["platform"],
            "spend":        spend,
            "limit":        b["budget_limit"],
            "pct":          pct,
            "start_date":   b["start_date"],
            "end_date":     b["end_date"],
            "days_elapsed": days_elapsed,
            "total_days":   max(1, (end - start).days + 1),
            "is_alert":     pct >= 90,
        }
        alerts.append(item)

        if pct >= 90 and not b["alert_sent"]:
            conn = get_db()
            conn.execute(
                "UPDATE budget_settings SET alert_sent=1 WHERE user_id=? AND platform=?",
                (uid, b["platform"])
            )
            conn.commit()
            conn.close()

    return jsonify({"alerts": alerts})


# ── API: HISTORY ──────────────────────────────────────────────────────────────

@dashboard_bp.route("/api/history")
@login_required
def api_history():
    uid  = session["user_id"]
    conn = get_db()
    logs = conn.execute("""
        SELECT id, action, detail, ip, created_at
        FROM activity_logs
        WHERE user_id=? AND action != 'VIEW_DASHBOARD'
        ORDER BY created_at DESC
        LIMIT 100
    """, (uid,)).fetchall()
    conn.close()
    return jsonify([dict(l) for l in logs])