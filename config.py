"""
config.py — Cấu hình tập trung cho AdsAnalytics Pro
Tất cả biến môi trường và hằng số đều khai báo tại đây.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── PLATFORM CREDENTIALS ──────────────────────────────────────────────────────
FB_APP_ID            = os.getenv("FB_APP_ID", "")
FB_APP_SECRET        = os.getenv("FB_APP_SECRET", "")
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
TIKTOK_APP_ID        = os.getenv("TIKTOK_APP_ID", "")
TIKTOK_APP_SECRET    = os.getenv("TIKTOK_APP_SECRET", "")

# ── APP CONFIG ────────────────────────────────────────────────────────────────
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5000")
SECRET_KEY   = os.getenv("SECRET_KEY", "ads-dashboard-secret-2024")
DB_PATH      = "instance/dashboard.db"

# ── PLATFORM API ENDPOINTS ────────────────────────────────────────────────────
FB_AUTH_URL   = "https://www.facebook.com/v18.0/dialog/oauth"
FB_TOKEN_URL  = "https://graph.facebook.com/v18.0/oauth/access_token"
FB_API        = "https://graph.facebook.com/v18.0"
FB_SCOPES     = "ads_read,ads_management,read_insights"

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES    = (
    "https://www.googleapis.com/auth/userinfo.email "
    "https://www.googleapis.com/auth/userinfo.profile openid"
)

TIKTOK_AUTH_URL  = "https://business-api.tiktok.com/portal/auth"
TIKTOK_TOKEN_URL = "https://business-api.tiktok.com/open_api/v1.3/oauth2/access_token/"

# ── MOCK DATA CONFIG ──────────────────────────────────────────────────────────
MOCK_CFG = {
    "facebook": {"base": 6_200_000, "roas": 3.1},
    "google":   {"base": 4_500_000, "roas": 4.2},
    "tiktok":   {"base": 1_800_000, "roas": 3.8},
}