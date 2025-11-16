from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional, Tuple
import sqlite3
from config import Config
from utils import escape_html

class Keyboards:
    """Класс для создания клавиатур бота."""
    def get_main_menu(self) -> InlineKeyboardMarkup:
        """Создание главного меню."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Купить", callback_data="buy_select_type")],
            [InlineKeyboardButton(text="📦 Продать", callback_data="sell")]
        ])

    def get_type_selection_menu_buy(self) -> InlineKeyboardMarkup:
        """Создание меню выбора типа для покупки."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Товары", callback_data="buy_type_product")],
            [InlineKeyboardButton(text="🛠 Услуги", callback_data="buy_type_service")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])


    def get_type_selection_menu_sell(self) -> InlineKeyboardMarkup:
        """Создание меню выбора типа для продажи."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Товар", callback_data="sell_type_product")],
            [InlineKeyboardButton(text="🛠 Услуга", callback_data="sell_type_service")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
        ])

    def get_back_to_main_menu(self) -> InlineKeyboardMarkup:
        """Создание клавиатуры с кнопкой возврата в главное меню."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
        ])

    def get_products(self, page: int = 0, item_type: Optional[str] = None) -> Tuple[InlineKeyboardMarkup, int]:
        """Получение списка товаров/услуг с пагинацией."""
        try:
            with sqlite3.connect("db.sqlite3") as conn:
                cur = conn.cursor()
                query = "SELECT id, name FROM products WHERE status = 'approved'"
                params = []
                if item_type:
                    query += " AND type = ?"
                    params.append(item_type)
                query += " ORDER BY id DESC"
                cur.execute(query, params)
                rows = cur.fetchall()
                total = len(rows)
                start = page * Config.PAGE_SIZE
                end = start + Config.PAGE_SIZE
                page_rows = rows[start:end]
                kb_rows = [
                    [InlineKeyboardButton(text=f"{r[0]}. {escape_html(r[1])}", callback_data=f"product_{r[0]}")]
                    for r in page_rows
                ]
                nav_buttons = []
                if page > 0:
                    nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"page_{page-1}_{item_type or 'all'}"))
                if end < total:
                    nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"page_{page+1}_{item_type or 'all'}"))
                nav_buttons.append(InlineKeyboardButton(text="🔙 Назад", callback_data="buy_select_type"))
                kb_rows.append(nav_buttons)
                return InlineKeyboardMarkup(inline_keyboard=kb_rows), total
        except Exception as e:
            logger.error(f"Ошибка в get_products: {e}")
            return InlineKeyboardMarkup(inline_keyboard=[]), 0