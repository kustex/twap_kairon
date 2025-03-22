import sqlite3
import threading
from pathlib import Path

DB_FILE = Path("twap_jobs.db")
DB_LOCK = threading.Lock()

def init_storage():
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # Create table to track submitted orders
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

        # Create table to track real fills (optional)
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

        conn.commit()

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
