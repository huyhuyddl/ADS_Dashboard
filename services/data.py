"""
services/data.py — Tổng hợp dữ liệu từ tất cả platform
Điều phối giữa API thật và mock data.
"""
from datetime import datetime
from database import get_db
from services.helpers import get_connections, token_expired
from services.mock import mock_platform
from services.facebook import fb_fetch
from services.google import google_fetch
from services.tiktok import tiktok_fetch

# Map platform → fetcher function
_FETCHERS = {
    "facebook": fb_fetch,
    "google":   google_fetch,
    "tiktok":   tiktok_fetch,
}


def get_platform_data(uid: int, platform: str, days: int = 7, force_mock: bool = False) -> dict:
    """
    Lấy data cho 1 platform.
    Thứ tự ưu tiên: force_mock → chưa kết nối → API thật → mock fallback
    """
    connections = get_connections(uid)
    row = connections.get(platform)

    # Chưa kết nối hoặc force mock
    if force_mock or not row:
        data = mock_platform(uid, platform, days)
        data["is_mock"]      = True
        data["is_connected"] = bool(row)
        data["needs_reauth"] = False
        return data

    # Thử lấy data thật
    real = _FETCHERS[platform](uid, row, days)
    if real:
        real["is_mock"]      = False
        real["is_connected"] = True
        real["needs_reauth"] = False
        # Cập nhật last_synced
        conn = get_db()
        conn.execute(
            "UPDATE platform_connections SET last_synced=? WHERE user_id=? AND platform=?",
            (datetime.now().isoformat(), uid, platform)
        )
        conn.commit()
        conn.close()
        return real

    # Fallback về mock (đã kết nối nhưng API không trả về data)
    data = mock_platform(uid, platform, days)
    data["is_mock"]      = True
    data["is_connected"] = True
    data["needs_reauth"] = token_expired(row)
    return data


def get_all_data(uid: int, days: int = 7, force_mock: bool = False) -> dict:
    """
    Tổng hợp data từ cả 3 platform theo format v2.
    Dùng cho dashboard chính và admin preview.
    """
    platforms = {
        p: get_platform_data(uid, p, days, force_mock)
        for p in ["facebook", "google", "tiktok"]
    }

    total_spend   = sum(p["total_spend"]   for p in platforms.values())
    total_revenue = sum(p["total_revenue"] for p in platforms.values())
    total_clicks  = sum(p["clicks"]        for p in platforms.values())

    labels = platforms["facebook"]["labels"]
    merged = [
        round(sum(platforms[p]["spend_series"][i] for p in platforms), 2)
        for i in range(len(labels))
    ]

    spend_series = {
        "facebook": platforms["facebook"]["spend_series"],
        "google":   platforms["google"]["spend_series"],
        "tiktok":   platforms["tiktok"]["spend_series"],
        "merged":   merged,
    }

    channel_stats = {
        p: {
            "spend":        platforms[p]["total_spend"],
            "revenue":      platforms[p]["total_revenue"],
            "roas":         platforms[p]["roas"],
            "roi":          platforms[p]["roi"],
            "cpa":          platforms[p]["cpa"],
            "clicks":       platforms[p]["clicks"],
            "impressions":  platforms[p]["impressions"],
            "ctr":          platforms[p]["ctr"],
            "is_mock":      platforms[p]["is_mock"],
            "is_connected": platforms[p]["is_connected"],
        }
        for p in ["facebook", "google", "tiktok"]
    }

    connected = get_connections(uid)

    return {
        "source":          "mixed" if any(not p["is_mock"] for p in platforms.values()) else "mock",
        "labels":          labels,
        "spend_series":    spend_series,
        "total_spend":     round(total_spend),
        "total_revenue":   round(total_revenue),
        "roas":            round(total_revenue / total_spend, 2) if total_spend else 0,
        "roi":             round((total_revenue - total_spend) / total_spend * 100, 1) if total_spend else 0,
        "cpa":             round(total_spend / total_clicks) if total_clicks else 0,
        "channel_stats":   channel_stats,
        "platforms":       platforms,
        "connected_count": len(connected),
    }