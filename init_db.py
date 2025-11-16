import sqlite3

# создаём (или подключаемся, если уже есть) файл базы
conn = sqlite3.connect("db.sqlite3")
cur = conn.cursor()

# создаём таблицу товаров
cur.execute("""
CREATE TABLE IF NOT EXISTS products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER,
    name TEXT,
    description TEXT,
    price TEXT,
    contact TEXT,
    photo TEXT,
    status TEXT,
    channel_message_id INTEGER,
    type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    photo TEXT,
    channel_message_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    can_sell INTEGER DEFAULT 1
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    seller_id INTEGER,
    buyer_id INTEGER,
    status TEXT,
    buyer_message_id INTEGER,
    seller_message_id INTEGER,
    seller_confirmed INTEGER DEFAULT 0,
    buyer_confirmed INTEGER DEFAULT 0
)
""")




conn.commit()
conn.close()

print("✅ Таблица products создана!")
