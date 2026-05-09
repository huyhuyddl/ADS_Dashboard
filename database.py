"""
database.py — Quản lý SQLite database
Bao gồm: kết nối, khởi tạo schema, seed data mặc định.
"""
import os
import sqlite3
import hashlib
from datetime import datetime
from config import DB_PATH


def get_db():
    """Trả về connection với row_factory đã set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    """Tạo schema và seed dữ liệu mặc định nếu chưa có."""
    os.makedirs("instance", exist_ok=True)
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT UNIQUE NOT NULL,
            email      TEXT UNIQUE NOT NULL,
            password   TEXT NOT NULL,
            role       TEXT DEFAULT 'user',
            is_active  INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT
        );

        CREATE TABLE IF NOT EXISTS platform_connections (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            platform     TEXT NOT NULL,
            access_token  TEXT,
            refresh_token TEXT,
            expires_at   TEXT,
            account_id   TEXT,
            account_name TEXT,
            scopes       TEXT,
            is_active    INTEGER DEFAULT 1,
            connected_at TEXT DEFAULT (datetime('now')),
            last_synced  TEXT,
            UNIQUE(user_id, platform),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS activity_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            action     TEXT,
            detail     TEXT,
            ip         TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER,
            platform      TEXT,
            monthly_limit REAL,
            month         TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS budget_settings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            platform     TEXT NOT NULL,
            budget_limit REAL NOT NULL,
            start_date   TEXT NOT NULL,
            end_date     TEXT NOT NULL,
            alert_sent   INTEGER DEFAULT 0,
            created_at   TEXT DEFAULT (datetime('now')),
            updated_at   TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, platform),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # ── Seed users mặc định ───────────────────────────────────────────────────
    default_users = [
        ("admin",       "admin@ads.com",        hash_pw("admin123"), "admin"),
        ("nguyen_van_a","vana@company.com",      hash_pw("user123"),  "user"),
        ("tran_thi_b",  "thib@agency.com",       hash_pw("user123"),  "user"),
        ("le_van_c",    "vanc@shop.com",         hash_pw("user123"),  "user"),
    ]
    for u in default_users:
        try:
            c.execute(
                "INSERT INTO users (username,email,password,role) VALUES (?,?,?,?)", u
            )
        except sqlite3.IntegrityError:
            pass  # Đã tồn tại

    # ── Seed budgets mặc định ─────────────────────────────────────────────────
    month = datetime.now().strftime("%Y-%m")
    default_budgets = [
        (2, "facebook", 50_000_000, month),
        (2, "google",   50_000_000, month),
        (2, "tiktok",   17_000_000, month),
        (3, "facebook", 30_000_000, month),
        (3, "google",   20_000_000, month),
    ]
    for b in default_budgets:
        try:
            c.execute(
                "INSERT INTO budgets (user_id,platform,monthly_limit,month) VALUES (?,?,?,?)", b
            )
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()