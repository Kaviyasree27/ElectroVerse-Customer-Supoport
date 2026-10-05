import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "ecommerce.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force_reseed=False):
    conn = get_db()
    cursor = conn.cursor()

    if force_reseed:
        cursor.execute("DROP TABLE IF EXISTS products")
        cursor.execute("DROP TABLE IF EXISTS orders")

    # 1. Products Catalog Table (Pure Electronic Devices Alone)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        currency TEXT DEFAULT '₹',
        stock INTEGER NOT NULL,
        description TEXT NOT NULL,
        specs TEXT NOT NULL,  -- JSON string
        image_url TEXT NOT NULL
    )
    """)

    # 2. Customer Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        customer_name TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        order_date TEXT NOT NULL,
        delivery_date TEXT,
        status TEXT NOT NULL,
        tracking_number TEXT,
        carrier TEXT,
        items TEXT NOT NULL,
        total_amount REAL NOT NULL,
        currency TEXT DEFAULT '₹',
        return_status TEXT DEFAULT 'None'
    )
    """)

    # 3. Chat Sessions & Persistent Memory Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_name TEXT DEFAULT 'Customer',
        user_email TEXT,
        order_id TEXT,
        created_at TEXT NOT NULL,
        last_active TEXT NOT NULL,
        is_human_handoff INTEGER DEFAULT 0,
        handoff_reason TEXT,
        summary TEXT
    )
    """)
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN user_email TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN order_id TEXT")
    except Exception:
        pass

    # 4. Chat Messages History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        sender TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    )
    """)

    # 5. Human Handoff Live Queue (Tickets)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS handoff_tickets (
        ticket_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        sentiment TEXT NOT NULL,
        priority TEXT NOT NULL,
        trigger_reason TEXT NOT NULL,
        summary TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        created_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    )
    """)

    # 6. Customer Cart Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cart_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        added_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
    """)

    # 7. Users Table for Customer Login & Admin Dashboard Access
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'customer',
        created_at TEXT NOT NULL
    )
    """)

    # Seed Static Admin User (admin123@gmail.com / admin27)
    cursor.execute("""
    INSERT OR IGNORE INTO users (email, password, name, role, created_at)
    VALUES ('admin123@gmail.com', 'admin27', 'System Administrator', 'admin', datetime('now'))
    """)

    # Seed Default Customer User (alex@gmail.com / password123)
    cursor.execute("""
    INSERT OR IGNORE INTO users (email, password, name, role, created_at)
    VALUES ('alex@gmail.com', 'password123', 'Alex Morgan', 'customer', datetime('now'))
    """)

    conn.commit()
    seed_products_catalog(conn)
    conn.close()

def seed_products_catalog(conn):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products")

    from .products_data import products

    cursor.executemany("""
    INSERT INTO products (id, name, category, price, currency, stock, description, specs, image_url)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, products)

    # Mock orders matching the electronic catalog:
    now = datetime.now()
    orders = [
        (
            "ORD-1001",
            "Alex Morgan",
            "alex@gmail.com",
            (now - timedelta(days=6)).strftime("%Y-%m-%d"),
            (now - timedelta(days=3)).strftime("%Y-%m-%d"),
            "Delivered",
            "FEDEX-8829410",
            "FedEx Ground",
            json.dumps([{"product_id": "HDP-009", "name": "JBL Live 660NC Wireless Over-Ear ANC", "qty": 1, "price": 7999.00}]),
            7999.00,
            "₹",
            "None"
        ),
        (
            "ORD-1002",
            "Jordan Reed",
            "jordan.r@example.com",
            (now - timedelta(days=50)).strftime("%Y-%m-%d"),
            (now - timedelta(days=45)).strftime("%Y-%m-%d"),
            "Delivered",
            "UPS-3391024",
            "UPS Standard",
            json.dumps([{"product_id": "HDP-001", "name": "Sony WH-1000XM5 Noise Cancelling Headphones", "qty": 1, "price": 29990.00}]),
            29990.00,
            "₹",
            "None"
        ),
        (
            "ORD-1003",
            "Taylor Swift",
            "taylor.s@example.com",
            (now - timedelta(days=4)).strftime("%Y-%m-%d"),
            (now - timedelta(days=2)).strftime("%Y-%m-%d"),
            "Delivered",
            "DHL-7710294",
            "DHL Express",
            json.dumps([{"product_id": "LAP-006", "name": "Apple MacBook Air 13\" M3", "qty": 1, "price": 99990.00}]),
            99990.00,
            "₹",
            "None"
        ),
        (
            "ORD-1004",
            "Marcus Vance",
            "marcus.v@example.com",
            (now - timedelta(days=2)).strftime("%Y-%m-%d"),
            None,
            "In Transit",
            "BLUEDART-9901423",
            "BlueDart Air Express",
            json.dumps([{"product_id": "PHN-004", "name": "OnePlus 13 Hasselblad 5G", "qty": 1, "price": 69999.00}]),
            69999.00,
            "₹",
            "None"
        ),
        (
            "ORD-1008",
            "kishore",
            "kishore@gmail.com",
            (now - timedelta(days=5)).strftime("%Y-%m-%d"),
            (now - timedelta(days=2)).strftime("%Y-%m-%d"),
            "Delivered",
            "BLUEDART-5519283",
            "BlueDart Express",
            json.dumps([{"product_id": "HDP-007", "name": "Apple AirPods Pro 2 USB-C", "qty": 1, "price": 24900.00}]),
            24900.00,
            "₹",
            "None"
        ),
        (
            "ORD-1009",
            "kishore",
            "kishore@gmail.com",
            now.strftime("%Y-%m-%d"),
            (now + timedelta(days=3)).strftime("%Y-%m-%d"),
            "Placed",
            "BLUEDART-7728192",
            "BlueDart Express",
            json.dumps([{"product_id": "HDP-005", "name": "Marshall Major IV Wireless Bluetooth Headphones", "qty": 1, "price": 12999.00}]),
            12999.00,
            "₹",
            "None"
        ),
        (
            "ORD-1010",
            "abhi",
            "abhi@gmail.com",
            now.strftime("%Y-%m-%d"),
            (now + timedelta(days=3)).strftime("%Y-%m-%d"),
            "In Transit",
            "BLUEDART-6193647",
            "BlueDart Express",
            json.dumps([{"product_id": "LAP-001", "name": "Apple MacBook Pro 16\" M3 Max", "qty": 1, "price": 249990.00}]),
            249990.00,
            "₹",
            "None"
        )
    ]

    for o in orders:
        cursor.execute("""
        INSERT OR REPLACE INTO orders (id, customer_name, customer_email, order_date, delivery_date, status, tracking_number, carrier, items, total_amount, currency, return_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, o)

    conn.commit()

if __name__ == "__main__":
    init_db(force_reseed=True)
    print("Electronic devices alone seeded successfully: 10 Laptops, 10 Phones, 10 Headphones, 10 Electronic Devices (40 total) with 100% unique image cards!")
