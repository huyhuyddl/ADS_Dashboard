"""
services/tiktok.py — TikTok Ads integration
Xử lý: OAuth token refresh, fetch data (TODO khi có App ID approved).
"""
from datetime import datetime, timedelta
from config import TIKTOK_APP_ID, TIKTOK_APP_SECRET, TIKTOK_TOKEN_URL
from services.helpers import http_post, save_connection


def tiktok_refresh(uid: int, row: dict):
    """Dùng refresh_token để lấy access_token mới."""
    if not row.get("refresh_token"):
        return None
    try:
        data = http_post(TIKTOK_TOKEN_URL, {
            "app_id":        TIKTOK_APP_ID,
            "secret":        TIKTOK_APP_SECRET,
            "refresh_token": row["refresh_token"],
            "grant_type":    "refresh_token",
        }).get("data", {})

        exp = (
            datetime.now() + timedelta(seconds=data.get("access_token_expire_in", 7_776_000))
        ).isoformat()

        save_connection(
            uid, "tiktok",
            data["access_token"],
            data.get("refresh_token", row["refresh_token"]),
            exp, row["account_id"], row["account_name"]
        )
        return data["access_token"]
    except Exception as e:
        print(f"[TikTok Refresh] {e}")
        return None


def tiktok_fetch(uid: int, row: dict, days: int = 7):
    """
    TODO: Implement TikTok Ads API khi App được approved.
    Hiện tại trả về None → dùng mock data.
    """
    return None