"""
routes/platforms.py — OAuth flow cho 3 nền tảng
Facebook, Google, TikTok: auth redirect + callback + disconnect + refresh.
"""
import json
import secrets
import urllib.parse
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, session, redirect, url_for

from config import (
    FB_APP_ID, FB_APP_SECRET, FB_AUTH_URL, FB_TOKEN_URL, FB_API, FB_SCOPES,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_AUTH_URL, GOOGLE_TOKEN_URL, GOOGLE_SCOPES,
    TIKTOK_APP_ID, TIKTOK_APP_SECRET, TIKTOK_AUTH_URL, TIKTOK_TOKEN_URL,
    APP_BASE_URL,
)
from services.helpers import (
    get_connections, save_connection, disconnect_platform,
    log_activity, token_expired,
)
from services.facebook import fb_to_long_lived, fb_refresh
from services.google import google_refresh, google_get_account_info
from services.tiktok import tiktok_refresh

platforms_bp = Blueprint("platforms", __name__)


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════════════════════
# DISCONNECT & REFRESH
# ══════════════════════════════════════════════════════════════════════════════

@platforms_bp.route("/api/disconnect/<platform>", methods=["POST"])
@login_required
def api_disconnect(platform):
    if platform not in ("facebook", "google", "tiktok"):
        return jsonify({"error": "Invalid platform"}), 400
    disconnect_platform(session["user_id"], platform)
    log_activity(session["user_id"], "DISCONNECT_PLATFORM", f"Ngắt kết nối {platform}")
    return jsonify({"ok": True})


@platforms_bp.route("/api/refresh/<platform>", methods=["POST"])
@login_required
def api_refresh_token(platform):
    if platform not in ("facebook", "google", "tiktok"):
        return jsonify({"error": "Invalid platform"}), 400

    uid  = session["user_id"]
    conns = get_connections(uid)
    row  = conns.get(platform)
    if not row:
        return jsonify({"error": "Chưa kết nối"}), 404

    if platform == "facebook":
        try:
            new_tok, new_exp = fb_to_long_lived(row["access_token"])
            save_connection(uid, "facebook", new_tok, None, new_exp,
                            row["account_id"], row["account_name"], row.get("scopes", "[]"))
            log_activity(uid, "FB_TOKEN_REFRESH", "Manual refresh OK")
            exp_dt    = datetime.fromisoformat(new_exp)
            days_left = max(0, (exp_dt - datetime.now()).days)
            return jsonify({"ok": True, "days_left": days_left,
                            "message": f"Token Facebook làm mới thành công! Còn {days_left} ngày."})
        except Exception as e:
            return jsonify({"error": "Token hết hạn, cần kết nối lại"}), 400

    elif platform == "google":
        if not row.get("refresh_token"):
            return jsonify({"error": "Không có refresh token", "needs_reauth": True}), 400
        new_tok = google_refresh(uid, row)
        if not new_tok:
            return jsonify({"error": "Không thể làm mới", "needs_reauth": True}), 400
        log_activity(uid, "GOOGLE_TOKEN_REFRESH", "Manual refresh OK")
        return jsonify({"ok": True, "message": "Token Google làm mới thành công!"})

    elif platform == "tiktok":
        if not row.get("refresh_token"):
            return jsonify({"error": "Không có refresh token", "needs_reauth": True}), 400
        new_tok = tiktok_refresh(uid, row)
        if not new_tok:
            return jsonify({"error": "Không thể làm mới", "needs_reauth": True}), 400
        log_activity(uid, "TIKTOK_TOKEN_REFRESH", "Manual refresh OK")
        return jsonify({"ok": True, "message": "Token TikTok làm mới thành công!"})


# ══════════════════════════════════════════════════════════════════════════════
# FACEBOOK OAUTH
# ══════════════════════════════════════════════════════════════════════════════

@platforms_bp.route("/auth/facebook")
@login_required
def auth_facebook():
    if not FB_APP_ID:
        return jsonify({"error": "FB_APP_ID chưa cấu hình trong .env"}), 503
    state = secrets.token_urlsafe(16)
    session["oauth_state_fb"] = state
    params = urllib.parse.urlencode({
        "client_id":    FB_APP_ID,
        "redirect_uri": f"{APP_BASE_URL}/auth/facebook/callback",
        "scope":        FB_SCOPES,
        "state":        state,
        "response_type": "code",
    })
    return redirect(f"{FB_AUTH_URL}?{params}")


@platforms_bp.route("/auth/facebook/callback")
@login_required
def auth_facebook_callback():
    if request.args.get("state") != session.pop("oauth_state_fb", None):
        return redirect(url_for("dashboard.dashboard_page") + "?error=invalid_state")
    error = request.args.get("error")
    if error:
        return redirect(url_for("dashboard.dashboard_page") + f"?error={error}")
    code = request.args.get("code")
    if not code:
        return redirect(url_for("dashboard.dashboard_page") + "?error=no_code")

    try:
        from services.helpers import http_get
        params = urllib.parse.urlencode({
            "client_id":     FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "redirect_uri":  f"{APP_BASE_URL}/auth/facebook/callback",
            "code":          code,
        })
        short     = http_get(f"{FB_TOKEN_URL}?{params}")["access_token"]
        long_tok, expires_at = fb_to_long_lived(short)
        me        = http_get(f"{FB_API}/me?fields=id,name&access_token={long_tok}")
        accounts  = http_get(f"{FB_API}/me/adaccounts?fields=id,name,account_status&access_token={long_tok}")
        ad_list   = accounts.get("data", [])
        active    = next((a for a in ad_list if a.get("account_status") == 1),
                         ad_list[0] if ad_list else None)
        account_id   = active["id"] if active else ""
        account_name = active.get("name", "") if active else me.get("name", "")
        save_connection(session["user_id"], "facebook", long_tok, None, expires_at,
                        account_id, account_name, json.dumps(FB_SCOPES.split(",")))
        log_activity(session["user_id"], "CONNECT_PLATFORM",
                     f"Facebook: {account_name} ({account_id})")
        return redirect(url_for("dashboard.dashboard_page") + "?connected=facebook")
    except Exception as e:
        print(f"[FB Callback] {e}")
        return redirect(url_for("dashboard.dashboard_page") + "?error=fb_oauth_failed")


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE OAUTH
# ══════════════════════════════════════════════════════════════════════════════

@platforms_bp.route("/auth/google")
@login_required
def auth_google():
    if not GOOGLE_CLIENT_ID:
        return jsonify({"error": "Chưa cấu hình GOOGLE_CLIENT_ID trong .env"}), 503
    state = secrets.token_urlsafe(16)
    session["oauth_state_google"] = state
    params = urllib.parse.urlencode({
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  f"{APP_BASE_URL}/auth/google/callback",
        "scope":         GOOGLE_SCOPES,
        "state":         state,
        "response_type": "code",
        "access_type":   "offline",
        "prompt":        "consent",
    })
    return redirect(f"{GOOGLE_AUTH_URL}?{params}")


@platforms_bp.route("/auth/google/callback")
@login_required
def auth_google_callback():
    if request.args.get("state") != session.pop("oauth_state_google", None):
        return redirect(url_for("dashboard.dashboard_page") + "?error=invalid_state")
    code = request.args.get("code")
    if not code:
        return redirect(url_for("dashboard.dashboard_page") +
                        f"?error={request.args.get('error', 'no_code')}")
    try:
        from services.helpers import http_post as _post
        data = _post(GOOGLE_TOKEN_URL, {
            "code":          code,
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri":  f"{APP_BASE_URL}/auth/google/callback",
            "grant_type":    "authorization_code",
        })
        # Set 7 ngày cho UI (access token thật sống 1h, nhưng có refresh token)
        exp          = (datetime.now() + timedelta(days=7)).isoformat()
        account_name, account_email = google_get_account_info(data["access_token"])
        save_connection(session["user_id"], "google",
                        data["access_token"], data.get("refresh_token", ""),
                        exp, account_email, account_name)
        log_activity(session["user_id"], "CONNECT_PLATFORM", "Google OK")
        return redirect(url_for("dashboard.dashboard_page") + "?connected=google")
    except Exception as e:
        print(f"[Google Callback] {e}")
        return redirect(url_for("dashboard.dashboard_page") + "?error=google_oauth_failed")


# ══════════════════════════════════════════════════════════════════════════════
# TIKTOK OAUTH
# ══════════════════════════════════════════════════════════════════════════════

@platforms_bp.route("/auth/tiktok")
@login_required
def auth_tiktok():
    if not TIKTOK_APP_ID:
        return jsonify({"error": "Chưa cấu hình TIKTOK_APP_ID trong .env"}), 503
    state = secrets.token_urlsafe(16)
    session["oauth_state_tiktok"] = state
    params = urllib.parse.urlencode({
        "app_id":       TIKTOK_APP_ID,
        "redirect_uri": f"{APP_BASE_URL}/auth/tiktok/callback",
        "state":        state,
    })
    return redirect(f"{TIKTOK_AUTH_URL}?{params}")


@platforms_bp.route("/auth/tiktok/callback")
@login_required
def auth_tiktok_callback():
    if request.args.get("state") != session.pop("oauth_state_tiktok", None):
        return redirect(url_for("dashboard.dashboard_page") + "?error=invalid_state")
    code = request.args.get("auth_code") or request.args.get("code")
    if not code:
        return redirect(url_for("dashboard.dashboard_page") + "?error=no_code")
    try:
        from services.helpers import http_post as _post
        data = _post(TIKTOK_TOKEN_URL, {
            "app_id":    TIKTOK_APP_ID,
            "secret":    TIKTOK_APP_SECRET,
            "auth_code": code,
        }).get("data", {})
        exp = (datetime.now() + timedelta(
            seconds=data.get("access_token_expire_in", 7_776_000)
        )).isoformat()
        save_connection(session["user_id"], "tiktok",
                        data["access_token"], data.get("refresh_token", ""),
                        exp, str(data.get("advertiser_id", "")), "TikTok Ads Account")
        log_activity(session["user_id"], "CONNECT_PLATFORM", "TikTok OK")
        return redirect(url_for("dashboard.dashboard_page") + "?connected=tiktok")
    except Exception as e:
        print(f"[TikTok Callback] {e}")
        return redirect(url_for("dashboard.dashboard_page") + "?error=tiktok_oauth_failed")