import sqlite3
import threading
import logging

from pathlib import Path
from datetime import datetime

DB_FILE = Path("twap_jobs.db")
DB_LOCK = threading.Lock()

def init_storage():
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # Submitted orders placed via scheduler/executor
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS submitted_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                exchange TEXT,
                symbol TEXT,
                price_at_submit REAL,
                size REAL,
                side TEXT,
                order_type TEXT,
                job_id TEXT,
                trade_number INTEGER,
                num_trades INTEGER
            )
        """)

        # Executed orders (optional: ccxt order response after submission)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS executed_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                exchange TEXT,
                symbol TEXT,
                price REAL,
                size REAL,
                side TEXT,
                order_type TEXT,
                job_id TEXT,
                raw_response TEXT
            )
        """)

        # Scheduled TWAP jobs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                exchange TEXT,
                symbol TEXT,
                side TEXT,
                total_size REAL,
                num_trades INTEGER,
                delay_seconds REAL,
                testnet BOOLEAN,
                price_limit REAL,
                timestamp TEXT
            )
        """)
        conn.commit()


# ---------- Logging functions ----------
def log_submitted_order(entry: dict):
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO submitted_orders (
                timestamp, exchange, symbol, price_at_submit,
                size, side, order_type, job_id, trade_number, num_trades
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["timestamp"], entry["exchange"], entry["symbol"],
            entry["price_at_submit"], entry["size"], entry["side"],
            entry["order_type"], entry["job_id"], entry["trade_number"], entry["num_trades"]
        ))
        conn.commit()

def log_executed_order(entry: dict):
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO executed_orders (
                timestamp, exchange, symbol, price, size,
                side, order_type, job_id, raw_response
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["timestamp"], entry["exchange"], entry["symbol"],
            entry["price"], entry["size"], entry["side"],
            entry["order_type"], entry["job_id"], entry["raw_response"]
        ))
        conn.commit()

def log_scheduled_job(entry: dict):
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scheduled_jobs (
                job_id, exchange, symbol, side, total_size,
                num_trades, delay_seconds, testnet, price_limit, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["job_id"],
            entry["exchange"],
            entry["symbol"],
            entry["side"],
            entry["total_size"],
            entry["num_trades"],
            entry["delay_seconds"],
            entry["testnet"],
            entry["price_limit"],
            entry["timestamp"]
        ))
        conn.commit()

# ---------- Read/Query functions ----------
def get_submitted_orders(limit=50):
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM submitted_orders ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_executed_orders(limit=50):
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM executed_orders ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_scheduled_jobs(limit=50):
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scheduled_jobs ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

