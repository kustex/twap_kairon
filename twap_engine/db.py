# db.py
import sqlite3
import threading
from pathlib import Path

DB_FILE = Path("twap_jobs.db")
DB_LOCK = threading.Lock()

def init_db():
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # Create table for submitted trades
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
        conn.commit()

def save_submitted_order(order: dict):
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO submitted_orders (
                timestamp, exchange, symbol, price_at_submit,
                size, side, order_type, job_id, trade_number, num_trades
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order["timestamp"],
            order["exchange"],
            order["symbol"],
            order["price_at_submit"],
            order["size"],
            order["side"],
            order["order_type"],
            order.get("job_id"),
            order.get("trade_number"),
            order.get("num_trades")
        ))
        conn.commit()

def fetch_submitted_orders(limit=50):
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM submitted_orders ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]