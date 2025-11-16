import sqlite3
from typing import Optional, List, Tuple

class Database:
    def __init__(self, db_path: str):
        """Инициализация базы данных с указанным путем к файлу SQLite."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Инициализация структуры базы данных."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        can_sell INTEGER DEFAULT 1
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        seller_id INTEGER,
                        name TEXT,
                        description TEXT,
                        price TEXT,
                        contact TEXT,
                        photo TEXT,
                        status TEXT,
                        type TEXT,
                        channel_message_id INTEGER,
                        FOREIGN KEY(seller_id) REFERENCES users(user_id)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER,
                        seller_id INTEGER,
                        buyer_id INTEGER,
                        status TEXT,
                        seller_message_id INTEGER,
                        buyer_message_id INTEGER,
                        seller_confirmed INTEGER DEFAULT 0,
                        buyer_confirmed INTEGER DEFAULT 0,
                        FOREIGN KEY(product_id) REFERENCES products(id),
                        FOREIGN KEY(seller_id) REFERENCES users(user_id),
                        FOREIGN KEY(buyer_id) REFERENCES users(user_id)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        text TEXT,
                        photo TEXT,
                        channel_message_id INTEGER
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при инициализации базы данных: {e}")
            raise

    def can_user_sell(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь продавать."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT can_sell FROM users WHERE user_id=?", (user_id,))
                row = cur.fetchone()
                if row is None:
                    cur.execute("INSERT INTO users (user_id, can_sell) VALUES (?, ?)", (user_id, 1))
                    conn.commit()
                    return True
                return row[0] == 1
        except sqlite3.Error as e:
            print(f"Ошибка в can_user_sell для user_id={user_id}: {e}")
            return False

    def add_product(self, seller_id: int, data: dict) -> int:
        """Добавляет новый товар или услугу в базу данных."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO products (seller_id, name, description, price, contact, photo, status, type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        seller_id, data["name"], data["description"], data["price"],
                        data["contact"], data.get("photo"), "pending", data["type"]
                    )
                )
                product_id = cur.lastrowid
                conn.commit()
                return product_id
        except sqlite3.Error as e:
            print(f"Ошибка при добавлении продукта для seller_id={seller_id}: {e}")
            raise

    def get_product(self, product_id: int) -> Optional[Tuple[str, str, str, Optional[str], str]]:
        """Получает данные о товаре/услуге по ID для отображения покупателям."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name, price, description, photo, type FROM products WHERE id=? AND status='approved'",
                    (product_id,)
                )
                return cur.fetchone()
        except sqlite3.Error as e:
            print(f"Ошибка в get_product для product_id={product_id}: {e}")
            return None

    def get_product_any_status(self, product_id: int) -> Optional[Tuple[str, str, str, Optional[str], str]]:
        """Получает данные о товаре/услуге по ID независимо от статуса."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name, price, description, photo, type FROM products WHERE id=?",
                    (product_id,)
                )
                return cur.fetchone()
        except sqlite3.Error as e:
            print(f"Ошибка в get_product_any_status для product_id={product_id}: {e}")
            return None

    def get_seller_id(self, product_id: int) -> Optional[int]:
        """Получает ID продавца по ID продукта."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT seller_id FROM products WHERE id=?", (product_id,))
                row = cur.fetchone()
                return row[0] if row else None
        except sqlite3.Error as e:
            print(f"Ошибка в get_seller_id для product_id={product_id}: {e}")
            return None

    def update_product_status(self, product_id: int, status: str, channel_message_id: Optional[int] = None):
        """Обновляет статус продукта и, при необходимости, ID сообщения в канале."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                if channel_message_id:
                    cur.execute(
                        "UPDATE products SET status=?, channel_message_id=? WHERE id=?",
                        (status, channel_message_id, product_id)
                    )
                else:
                    cur.execute("UPDATE products SET status=? WHERE id=?", (status, product_id))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка в update_product_status для product_id={product_id}: {e}")
            raise

    def get_pending_products(self) -> List[Tuple[int, str, str, str]]:
        """Получает список товаров/услуг на модерации."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name, price, type FROM products WHERE status='pending'")
                return cur.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка в get_pending_products: {e}")
            return []

    def get_approved_products(self) -> List[Tuple[int, str, str, str]]:
        """Получает список активных товаров/услуг."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name, price, type FROM products WHERE status='approved'")
                return cur.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка в get_approved_products: {e}")
            return []

    def get_rejected_products(self) -> List[Tuple[int, str, str, str]]:
        """Получает список отклоненных товаров/услуг."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name, price, type FROM products WHERE status='rejected'")
                return cur.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка в get_rejected_products: {e}")
            return []

    def create_order(self, product_id: int, seller_id: int, buyer_id: int) -> int:
        """Создает новый заказ."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO orders (product_id, seller_id, buyer_id, status) VALUES (?, ?, ?, ?)",
                    (product_id, seller_id, buyer_id, "in_progress")
                )
                order_id = cur.lastrowid
                conn.commit()
                return order_id
        except sqlite3.Error as e:
            print(f"Ошибка в create_order для product_id={product_id}: {e}")
            raise

    def get_active_order_by_user(self, user_id: int) -> Optional[Tuple[int, int, int]]:
        """Получает активный заказ для пользователя (продавца или покупателя)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT product_id, seller_id, buyer_id
                    FROM orders
                    WHERE (seller_id=? OR buyer_id=?) AND status='in_progress'
                    LIMIT 1
                    """,
                    (user_id, user_id)
                )
                return cur.fetchone()
        except sqlite3.Error as e:
            print(f"Ошибка в get_active_order_by_user для user_id={user_id}: {e}")
            return None

    def update_order_message_id(self, order_id: int, seller_message_id: Optional[int] = None, buyer_message_id: Optional[int] = None):
        """Обновляет ID сообщений чата для заказа."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                if seller_message_id and buyer_message_id:
                    cur.execute(
                        "UPDATE orders SET seller_message_id=?, buyer_message_id=? WHERE id=?",
                        (seller_message_id, buyer_message_id, order_id)
                    )
                elif seller_message_id:
                    cur.execute("UPDATE orders SET seller_message_id=? WHERE id=?", (seller_message_id, order_id))
                elif buyer_message_id:
                    cur.execute("UPDATE orders SET buyer_message_id=? WHERE id=?", (buyer_message_id, order_id))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка в update_order_message_id для order_id={order_id}: {e}")
            raise

    def confirm_order(self, order_id: int, user_type: str) -> Optional[Tuple[bool, int, int, int]]:
        """Подтверждает сделку со стороны продавца или покупателя."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                field = "seller_confirmed" if user_type == "seller" else "buyer_confirmed"
                cur.execute(f"UPDATE orders SET {field}=1 WHERE id=?", (order_id,))
                cur.execute(
                    "SELECT seller_confirmed, buyer_confirmed, product_id, seller_id, buyer_id FROM orders WHERE id=?",
                    (order_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                seller_conf, buyer_conf, product_id, seller_id, buyer_id = row
                conn.commit()
                return bool(seller_conf), bool(buyer_conf), product_id, seller_id, buyer_id
        except sqlite3.Error as e:
            print(f"Ошибка в confirm_order для order_id={order_id}: {e}")
            return None

    def update_order_status(self, order_id: int, status: str):
        """Обновляет статус заказа."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка в update_order_status для order_id={order_id}: {e}")
            raise

    def get_order(self, order_id: int) -> Optional[Tuple[int, int, int, Optional[int], str]]:
        """Получает информацию о заказе по ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT product_id, seller_id, buyer_id, seller_message_id, status FROM orders WHERE id=?",
                    (order_id,)
                )
                return cur.fetchone()
        except sqlite3.Error as e:
            print(f"Ошибка в get_order для order_id={order_id}: {e}")
            return None

    def get_order_message_ids(self, order_id: int) -> Tuple[Optional[int], Optional[int]]:
        """Получает ID сообщений чата для заказа."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT buyer_message_id, seller_message_id FROM orders WHERE id=?", (order_id,))
                row = cur.fetchone()
                return (row[0], row[1]) if row else (None, None)
        except sqlite3.Error as e:
            print(f"Ошибка в get_order_message_ids для order_id={order_id}: {e}")
            return None, None

    def get_channel_message_id(self, product_id: int) -> Optional[int]:
        """Получает ID сообщения в канале для продукта."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT channel_message_id FROM products WHERE id=?", (product_id,))
                row = cur.fetchone()
                return row[0] if row else None
        except sqlite3.Error as e:
            print(f"Ошибка в get_channel_message_id для product_id={product_id}: {e}")
            return None

    def delete_product(self, product_id: int):
        """Удаляет товар или услугу из базы данных."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM products WHERE id=?", (product_id,))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка в delete_product для product_id={product_id}: {e}")
            raise

    def get_all_users(self) -> List[int]:
        """Получает список всех пользователей."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM users")
                return [row[0] for row in cur.fetchall()]
        except sqlite3.Error as e:
            print(f"Ошибка в get_all_users: {e}")
            return []

    def get_active_orders(self) -> List[Tuple[int, int, int, int, str]]:
        """Получает список активных заказов."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, product_id, seller_id, buyer_id, status FROM orders WHERE status='in_progress'")
                return cur.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка в get_active_orders: {e}")
            return []

    def get_stats(self) -> Tuple[int, int, int, int]:
        """Получает статистику: общее количество товаров, активных, проданных, пользователей."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM products")
                total_products = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM products WHERE status='approved'")
                active_products = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM products WHERE status='sold'")
                sold_products = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM users")
                total_users = cur.fetchone()[0]
                return total_products, active_products, sold_products, total_users
        except sqlite3.Error as e:
            print(f"Ошибка в get_stats: {e}")
            return 0, 0, 0, 0

    def get_user_info(self, user_id: int) -> Tuple[int, int, int]:
        """Получает информацию о пользователе: количество товаров, продаж, покупок."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM products WHERE seller_id=?", (user_id,))
                products_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM orders WHERE seller_id=? AND status='completed'", (user_id,))
                sold_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM orders WHERE buyer_id=? AND status='completed'", (user_id,))
                bought_count = cur.fetchone()[0]
                return products_count, sold_count, bought_count
        except sqlite3.Error as e:
            print(f"Ошибка в get_user_info для user_id={user_id}: {e}")
            return 0, 0, 0

    def ban_user(self, user_id: int):
        """Запрещает пользователю продавать."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("INSERT OR REPLACE INTO users (user_id, can_sell) VALUES (?, ?)", (user_id, 0))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка в ban_user для user_id={user_id}: {e}")
            raise

    def unban_user(self, user_id: int):
        """Разрешает пользователю продавать."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("INSERT OR REPLACE INTO users (user_id, can_sell) VALUES (?, ?)", (user_id, 1))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка в unban_user для user_id={user_id}: {e}")
            raise

    def get_top_sellers(self) -> List[Tuple[int, int]]:
        """Получает топ-10 продавцов по количеству продаж."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT seller_id, COUNT(*) as sales
                    FROM orders
                    WHERE status='completed'
                    GROUP BY seller_id
                    ORDER BY sales DESC
                    LIMIT 10
                    """
                )
                return cur.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка в get_top_sellers: {e}")
            return []

    def get_top_buyers(self) -> List[Tuple[int, int]]:
        """Получает топ-10 покупателей по количеству покупок."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT buyer_id, COUNT(*) as purchases
                    FROM orders
                    WHERE status='completed'
                    GROUP BY buyer_id
                    ORDER BY purchases DESC
                    LIMIT 10
                    """
                )
                return cur.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка в get_top_buyers: {e}")
            return []

    def create_ad(self, text: str, photo: Optional[str]) -> int:
        """Создает новый рекламный пост."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO ads (text, photo) VALUES (?, ?)", (text, photo))
                ad_id = cur.lastrowid
                conn.commit()
                return ad_id
        except sqlite3.Error as e:
            print(f"Ошибка в create_ad: {e}")
            raise

    def get_ad(self, ad_id: int) -> Optional[Tuple[str, Optional[str]]]:
        """Получает данные о рекламном посте по ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT text, photo FROM ads WHERE id=?", (ad_id,))
                return cur.fetchone()
        except sqlite3.Error as e:
            print(f"Ошибка в get_ad для ad_id={ad_id}: {e}")
            return None

    def update_ad_channel_message_id(self, ad_id: int, channel_message_id: int):
        """Обновляет ID сообщения в канале для рекламного поста."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("UPDATE ads SET channel_message_id=? WHERE id=?", (channel_message_id, ad_id))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка в update_ad_channel_message_id для ad_id={ad_id}: {e}")
            raise

    def get_ad_channel_message_id(self, ad_id: int) -> Optional[int]:
        """Получает ID сообщения в канале для рекламного поста."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT channel_message_id FROM ads WHERE id=?", (ad_id,))
                row = cur.fetchone()
                return row[0] if row else None
        except sqlite3.Error as e:
            print(f"Ошибка в get_ad_channel_message_id для ad_id={ad_id}: {e}")
            return None

    def delete_ad(self, ad_id: int):
        """Удаляет рекламный пост из базы данных."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM ads WHERE id=?", (ad_id,))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка в delete_ad для ad_id={ad_id}: {e}")
            raise

    def get_products(self, page: int, item_type: Optional[str] = None, page_size: int = 5) -> Tuple[List[Tuple[int, str, str, str]], int]:
        """Получает список товаров/услуг с пагинацией."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                query = "SELECT id, name, price, type FROM products WHERE status='approved'"
                params = []
                if item_type:
                    query += " AND type=?"
                    params.append(item_type)
                query += " ORDER BY id DESC LIMIT ? OFFSET ?"
                params.extend([page_size, page * page_size])
                cur.execute(query, params)
                products = cur.fetchall()
                cur.execute("SELECT COUNT(*) FROM products WHERE status='approved'" + (f" AND type='{item_type}'" if item_type else ""))
                total = cur.fetchone()[0]
                return products, total
        except sqlite3.Error as e:
            print(f"Ошибка в get_products для item_type={item_type}, page={page}: {e}")
            return [], 0