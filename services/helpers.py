"""
services/helpers.py — Tiện ích dùng chung cho các service
HTTP GET/POST, kiểm tra token hết hạn, lưu log hoạt động.
"""
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from flask import request
from database import get_db


# ── HTTP HELPERS ──────────────────────────────────────────────────────────────

def http_get(url: str, timeout: int = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def http_post(url: str, data: dict, timeout: int = 10) -> dict:
    payload = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


# ── TOKEN HELPERS ─────────────────────────────────────────────────────────────

def token_expired(row: dict) -> bool:
    """Trả về True nếu token đã hết hạn."""
    if not row.get("expires_at"):
        return False
    try:
        return datetime.now() > datetime.fromisoformat(row["expires_at"])
    except Exception:
        return False


def token_expiring(row: dict, days: int = 7) -> bool:
    """Trả về True nếu token sẽ hết hạn trong `days` ngày tới."""
    if not row.get("expires_at"):
        return False
    try:
        return datetime.now() > datetime.fromisoformat(row["expires_at"]) - timedelta(days=days)
    except Exception:
        return False


# ── ACTIVITY LOG ──────────────────────────────────────────────────────────────

def log_activity(user_id, action: str, detail: str = ""):
    conn = get_db()
    conn.execute(
        "INSERT INTO activity_logs (user_id,action,detail,ip) VALUES (?,?,?,?)",
        (user_id, action, detail, request.remote_addr),
    )
    conn.commit()
    conn.close()


# ── CONNECTION HELPERS ────────────────────────────────────────────────────────

def get_connections(user_id: int) -> dict:
    """Trả về dict {platform: row} cho user."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM platform_connections WHERE user_id=? AND is_active=1",
        (user_id,),
    ).fetchall()
    conn.close()
    return {r["platform"]: dict(r) for r in rows}


def save_connection(
    uid, platform, access_token, refresh_token,
    expires_at, account_id, account_name, scopes="[]"
):
    conn = get_db()
    conn.execute("""
        INSERT INTO platform_connections
            (user_id,platform,access_token,refresh_token,expires_at,
             account_id,account_name,scopes,is_active,connected_at)
        VALUES (?,?,?,?,?,?,?,?,1,datetime('now'))
        ON CONFLICT(user_id,platform) DO UPDATE SET
            access_token=excluded.access_token,
            refresh_token=excluded.refresh_token,
            expires_at=excluded.expires_at,
            account_id=excluded.account_id,
            account_name=excluded.account_name,
            scopes=excluded.scopes,
            is_active=1,
            connected_at=datetime('now')
    """, (uid, platform, access_token, refresh_token,
          expires_at, account_id, account_name, scopes))
    conn.commit()
    conn.close()


def disconnect_platform(uid: int, platform: str):
    conn = get_db()
    conn.execute(
        "UPDATE platform_connections SET is_active=0 WHERE user_id=? AND platform=?",
        (uid, platform),
    )
    conn.commit()
    conn.close()