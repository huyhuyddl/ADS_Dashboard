"""
services/google.py — Google Ads integration
Xử lý: OAuth token refresh, fetch data (TODO khi có Developer Token).
"""
from datetime import datetime, timedelta
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_TOKEN_URL
from services.helpers import http_post, http_get, save_connection


def google_refresh(uid: int, row: dict):
    """Dùng refresh_token để lấy access_token mới."""
    if not row.get("refresh_token"):
        return None
    try:
        data = http_post(GOOGLE_TOKEN_URL, {
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": row["refresh_token"],
            "grant_type":    "refresh_token",
        })
        exp = (datetime.now() + timedelta(seconds=data.get("expires_in", 3600))).isoformat()
        save_connection(
            uid, "google", data["access_token"],
            row["refresh_token"], exp,
            row["account_id"], row["account_name"]
        )
        return data["access_token"]
    except Exception as e:
        print(f"[Google Refresh] {e}")
        return None


def google_get_account_info(access_token: str) -> tuple[str, str]:
    """
    Lấy tên và email từ Google userinfo API.
    Trả về (account_name, account_email).
    """
    try:
        me = http_get(
            f"https://www.googleapis.com/oauth2/v2/userinfo?access_token={access_token}"
        )
        return me.get("name", "Google Account"), me.get("email", "")
    except Exception:
        return "Google Account", ""


def google_fetch(uid: int, row: dict, days: int = 7):
    """
    TODO: Implement Google Ads API khi có Developer Token.
    Hiện tại trả về None → dùng mock data.
    """
    return None