"""
services/facebook.py — Facebook Ads API integration
Xử lý: token exchange, auto-refresh, fetch insights data.
"""
import json
import urllib.parse
from datetime import datetime, timedelta

from config import FB_APP_ID, FB_APP_SECRET, FB_TOKEN_URL, FB_API
from database import get_db
from services.helpers import http_get, save_connection, log_activity, token_expired, token_expiring


# ── TOKEN ─────────────────────────────────────────────────────────────────────

def fb_to_long_lived(short_token: str) -> tuple[str, str]:
    """Đổi short-lived token lấy long-lived token (~60 ngày)."""
    params = urllib.parse.urlencode({
        "grant_type":      "fb_exchange_token",
        "client_id":       FB_APP_ID,
        "client_secret":   FB_APP_SECRET,
        "fb_exchange_token": short_token,
    })
    data = http_get(f"{FB_TOKEN_URL}?{params}")
    expires_at = (
        datetime.now() + timedelta(seconds=int(data.get("expires_in", 5_184_000)))
    ).isoformat()
    return data["access_token"], expires_at


def fb_refresh(uid: int, row: dict):
    """
    Tự động làm mới Facebook token.
    Nếu thất bại → đánh dấu is_active=0, yêu cầu kết nối lại.
    """
    try:
        new_token, new_exp = fb_to_long_lived(row["access_token"])
        save_connection(
            uid, "facebook", new_token, None, new_exp,
            row["account_id"], row["account_name"], row.get("scopes", "[]")
        )
        log_activity(uid, "FB_TOKEN_REFRESH", "Auto-refresh OK")
        return new_token
    except Exception as e:
        print(f"[FB Refresh] {e}")
        conn = get_db()
        conn.execute(
            "UPDATE platform_connections SET is_active=0 WHERE user_id=? AND platform='facebook'",
            (uid,)
        )
        conn.commit()
        conn.close()
        log_activity(uid, "FB_TOKEN_EXPIRED", "Token hết hạn, cần kết nối lại")
        return None


def get_valid_fb_token(uid: int, row: dict):
    """Trả về token hợp lệ, tự refresh nếu cần."""
    if token_expired(row):
        return fb_refresh(uid, row)
    if token_expiring(row, days=7):
        try:
            fb_refresh(uid, row)
        except Exception:
            pass
    return row["access_token"]


# ── DATA FETCH ────────────────────────────────────────────────────────────────

def fb_fetch(uid: int, row: dict, days: int = 7):
    """
    Lấy dữ liệu insights từ Facebook Ads API.
    Trả về None nếu không có data hoặc lỗi.
    """
    token = get_valid_fb_token(uid, row)
    if not token or not row.get("account_id"):
        return None

    date_end   = datetime.now().strftime("%Y-%m-%d")
    date_start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    url = (
        f"{FB_API}/{row['account_id']}/insights"
        f"?fields=spend,impressions,clicks,actions,action_values"
        f"&time_range={{\"since\":\"{date_start}\",\"until\":\"{date_end}\"}}"
        f"&time_increment=1&access_token={token}"
    )

    try:
        res = http_get(url)

        if "error" in res:
            code = res["error"].get("code")
            if code in (190, 102):
                fb_refresh(uid, row)
            return None

        rows = res.get("data", [])
        if not rows:
            return None

        labels, spend_series = [], []
        total_spend = total_revenue = clicks = impressions = 0

        for r in rows:
            labels.append(r.get("date_start", "")[-5:].replace("-", "/"))
            spend = float(r.get("spend", 0)) * 23_000
            spend_series.append(round(spend / 1_000_000, 2))
            total_spend  += spend
            clicks       += int(r.get("clicks", 0))
            impressions  += int(r.get("impressions", 0))
            for av in r.get("action_values", []):
                if av["action_type"] == "purchase":
                    total_revenue += float(av["value"]) * 23_000

        roas = round(total_revenue / total_spend, 2) if total_spend else 0
        roi  = round((total_revenue - total_spend) / total_spend * 100, 1) if total_spend else 0

        return {
            "platform":      "facebook",
            "source":        "api",
            "labels":        labels,
            "spend_series":  spend_series,
            "total_spend":   round(total_spend),
            "total_revenue": round(total_revenue),
            "roas":          roas,
            "roi":           roi,
            "cpa":           round(total_spend / clicks) if clicks else 0,
            "clicks":        clicks,
            "impressions":   impressions,
            "ctr":           round(clicks / max(impressions, 1) * 100, 2),
        }

    except Exception as e:
        print(f"[FB Fetch] {e}")
        return None