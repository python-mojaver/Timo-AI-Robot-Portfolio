import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = Path(os.getenv("TIMO_CATALOG_DB") or BASE_DIR / "products.db")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            product_code TEXT,
            product_name TEXT,
            color TEXT,
            size TEXT,
            description TEXT,
            price_rial REAL,
            price_toman REAL,
            available INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()

def get_sample_products(limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            category,
            product_code,
            product_name,
            color,
            size,
            price_toman
        FROM products
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return rows
def search_products(query, limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    like = f"%{query}%"

    cursor.execute("""
        SELECT *
        FROM products
        WHERE
            product_name LIKE ?
            OR description LIKE ?
            OR color LIKE ?
            OR size LIKE ?
            OR product_code LIKE ?
            OR category LIKE ?
        LIMIT ?
    """, (
        like,
        like,
        like,
        like,
        like,
        like,
        limit
    ))

    rows = cursor.fetchall()
    conn.close()

    return rows
