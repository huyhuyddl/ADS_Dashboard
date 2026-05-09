"""
services/mock.py — Tạo dữ liệu minh họa cho dashboard
Dùng khi chưa kết nối API thật hoặc API không trả về data.
"""
import random
from datetime import datetime, timedelta
from config import MOCK_CFG


def mock_platform(uid: int, platform: str, days: int = 7) -> dict:
    """
    Sinh dữ liệu mock nhất quán theo uid + platform.
    random.seed đảm bảo cùng uid/platform luôn ra cùng số.
    """
    cfg = MOCK_CFG[platform]
    random.seed(uid * 31 + list(MOCK_CFG).index(platform))

    labels, spend_series = [], []
    for i in range(days):
        d = datetime.now() - timedelta(days=days - 1 - i)
        labels.append(d.strftime("%d/%m"))
        spend_series.append(
            round(cfg["base"] * random.uniform(0.7, 1.3) / 1_000_000, 2)
        )

    total_spend   = sum(spend_series) * 1_000_000
    total_revenue = total_spend * random.uniform(2.8, 4.5)
    clicks        = random.randint(1_200, 8_000)
    impressions   = random.randint(80_000, 500_000)

    return {
        "platform":      platform,
        "source":        "mock",
        "labels":        labels,
        "spend_series":  spend_series,
        "total_spend":   round(total_spend),
        "total_revenue": round(total_revenue),
        "roas":          round(total_revenue / total_spend, 2),
        "roi":           round((total_revenue - total_spend) / total_spend * 100, 1),
        "cpa":           round(total_spend / clicks),
        "clicks":        clicks,
        "impressions":   impressions,
        "ctr":           round(clicks / impressions * 100, 2),
    }