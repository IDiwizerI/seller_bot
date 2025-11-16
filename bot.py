import asyncio
import logging
from typing import Optional, Tuple, List
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram import F
import os

from config import Config
from database import Database
from keyboards import Keyboards
from states import SellProduct, Chatting, LogsState
from utils import escape_html, log_user_message


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="bot.log"
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=Config.TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database("db.sqlite3")
keyboards = Keyboards()

# Обработчик команды /start
@dp.message(Command(commands=["start"]))
async def start(message: types.Message):
    """Обработка команды /start для запуска бота и отображения главного меню."""
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("product_"):
        try:
            product_id = int(args[1].split("_")[1])
            await show_product_card(message, product_id)
        except ValueError as e:
            logger.error(f"Ошибка при разборе product_id={args[1]}: {e}")
            await message.answer("❌ Ошибка при отображении товара.")
        return
    await message.answer(
        "Привет! Я бот Барахолки МГСУ.\nЧто хочешь сделать? 👇",
        reply_markup=keyboards.get_main_menu()
    )

# Обработчик команды /help
@dp.message(Command(commands=["help"]))
async def cmd_help(message: types.Message):
    """Отображение списка доступных команд для пользователей."""
    await message.answer(
        "Команды:\n/start - Запустить бота\n/help - Показать помощь",
        parse_mode="HTML"
    )

# Обработчик команды /help_admin
@dp.message(Command(commands=["help_admin"]))
async def cmd_help_admin(message: types.Message):
    """Отображение списка админских команд."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /help_admin от user_id={message.from_user.id}")
        return
    help_text = (
        "🛠 <b>Список админских команд:</b>\n"
        "/pending – товары и услуги на модерации\n"
        "/approved – активные товары и услуги\n"
        "/reject – отклонённые товары и услуги\n"
        "/delete <code>&lt;adv/post&gt;</code> <code>&lt;id&gt;</code> – удалить товар/услугу или рекламу\n"
        "/broadcast <code>&lt;текст&gt;</code> – рассылка\n"
        "/orders – активные сделки\n"
        "/close_order <code>&lt;id&gt;</code> – закрыть сделку\n"
        "/cancel_order <code>&lt;id&gt;</code> – отменить сделку\n"
        "/stats – статистика\n"
        "/user <code>&lt;user_id&gt;</code> – инфо о пользователе\n"
        "/logs – лог-файлы\n"
        "/db_backup – бэкап базы\n"
        "/ban <code>&lt;user_id&gt;</code> – запретить продажу\n"
        "/unban <code>&lt;user_id&gt;</code> – снять запрет\n"
        "/sellers – топ продавцов\n"
        "/buyers – топ покупателей\n"
        "/send_user <code>&lt;user_id&gt;</code> <code>&lt;текст&gt;</code> – ЛС пользователю\n"
        "/pin <code>&lt;id&gt;</code> – закрепить товар или услугу\n"
        "/unpin – открепить всё\n"
        "/adv <code>&lt;текст&gt;</code> – создать рекламный пост\n"
        "/send_adv <code>&lt;id_поста&gt;</code> <code>&lt;all/channel&gt;</code> – отправить рекламный пост\n"
        "/admins – список админов\n"
        "/add_admin <code>&lt;user_id&gt;</code> – добавить админа\n"
        "/remove_admin <code>&lt;user_id&gt;</code> – убрать админа"
    )
    await message.answer(help_text, parse_mode="HTML")

# Обработчик выбора типа для покупки
@dp.callback_query(lambda c: c.data == "buy_select_type")
async def buy_select_type(callback: types.CallbackQuery):
    """Отображение меню выбора типа покупки (товары/услуги)."""
    await callback.message.edit_text(
        "Что вы хотите купить?",
        reply_markup=keyboards.get_type_selection_menu_buy()
    )
    await callback.answer()

# Обработчик показа списка товаров/услуг
@dp.callback_query(lambda c: c.data in ["buy_type_product", "buy_type_service"])
async def show_items_list(callback: types.CallbackQuery):
    """Отображение списка товаров или услуг с пагинацией."""
    item_type = "product" if callback.data == "buy_type_product" else "service"
    kb, total = keyboards.get_products(page=0, item_type=item_type)
    type_label = "товаров" if item_type == "product" else "услуг"
    text = f"📋 Список {type_label}:" if total > 0 else f"❌ Нет доступных {type_label}."
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# Обработчик пагинации товаров
@dp.callback_query(lambda c: c.data.startswith("page_"))
async def paginate(callback: types.CallbackQuery):
    """Обработка пагинации списка товаров/услуг."""
    try:
        parts = callback.data.split("_")
        page = int(parts[1])
        item_type = parts[2] if len(parts) > 2 and parts[2] != "all" else None
        kb, total = keyboards.get_products(page, item_type)
        type_label = "товаров" if item_type == "product" else "услуг" if item_type == "service" else "товаров и услуг"
        await callback.message.edit_text(f"📋 Список {type_label}:", reply_markup=kb)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в paginate для callback_data={callback.data}: {e}")
        await callback.answer("❌ Ошибка при переключении страницы.", show_alert=True)

# Обработчик начала процесса продажи
@dp.callback_query(lambda c: c.data == "sell")
async def start_sell(callback: types.CallbackQuery, state: FSMContext):
    """Начало процесса добавления товара или услуги на продажу."""
    if not db.can_user_sell(callback.from_user.id):
        await callback.message.edit_text(
            "🚫 Вам запрещено продавать. Обратитесь к администрации.",
            reply_markup=keyboards.get_main_menu()
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        "Что вы хотите продать?",
        reply_markup=keyboards.get_type_selection_menu_sell()
    )
    await callback.answer()

# Обработчик выбора типа для продажи
@dp.callback_query(lambda c: c.data in ["sell_type_product", "sell_type_service"])
async def select_sell_type(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора типа продаваемого объекта (товар/услуга)."""
    item_type = "product" if callback.data == "sell_type_product" else "service"
    await state.update_data(type=item_type)
    await state.set_state(SellProduct.name)
    await callback.message.edit_text(
        "Напиши название:",
        reply_markup=keyboards.get_back_to_main_menu()
    )
    await callback.answer()

# Обработчики для пошагового ввода данных о товаре/услуге
@dp.message(SellProduct.name)
async def process_name(message: types.Message, state: FSMContext):
    """Сохранение названия товара/услуги."""
    if not db.can_user_sell(message.from_user.id):
        await message.answer("🚫 Вам запрещено продавать.", reply_markup=keyboards.get_main_menu())
        return
    await state.update_data(name=message.text)
    await state.set_state(SellProduct.description)
    await message.answer("✏️ Введи описание:", reply_markup=keyboards.get_back_to_main_menu())

@dp.message(SellProduct.description)
async def process_description(message: types.Message, state: FSMContext):
    """Сохранение описания товара/услуги."""
    if not db.can_user_sell(message.from_user.id):
        await message.answer("🚫 Вам запрещено продавать.", reply_markup=keyboards.get_main_menu())
        return
    await state.update_data(description=message.text)
    await state.set_state(SellProduct.price)
    await message.answer("💸 Введи цену:", reply_markup=keyboards.get_back_to_main_menu())

@dp.message(SellProduct.price)
async def process_price(message: types.Message, state: FSMContext):
    """Сохранение цены товара/услуги."""
    if not db.can_user_sell(message.from_user.id):
        await message.answer("🚫 Вам запрещено продавать.", reply_markup=keyboards.get_main_menu())
        return
    await state.update_data(price=message.text)
    await state.set_state(SellProduct.contact)
    await message.answer("📱 Введи контакт для связи:", reply_markup=keyboards.get_back_to_main_menu())

@dp.message(SellProduct.contact)
async def process_contact(message: types.Message, state: FSMContext):
    """Сохранение контактной информации."""
    if not db.can_user_sell(message.from_user.id):
        await message.answer("🚫 Вам запрещено продавать.", reply_markup=keyboards.get_main_menu())
        return
    await state.update_data(contact=message.text)
    await state.set_state(SellProduct.photo)
    await message.answer("📷 Отправь фото или напиши 'пропустить':", reply_markup=keyboards.get_back_to_main_menu())

@dp.message(SellProduct.photo)
async def process_photo(message: types.Message, state: FSMContext):
    """Сохранение фото и завершение создания объявления."""
    if not db.can_user_sell(message.from_user.id):
        await message.answer("🚫 Вам запрещено продавать.", reply_markup=keyboards.get_main_menu())
        return
    photo_id = None
    if message.text and message.text.lower() == 'пропустить':
        await state.update_data(photo=None)
    elif message.photo:
        photo_id = message.photo[-1].file_id
        await state.update_data(photo=photo_id)
        log_user_message(message.from_user.id, "user", "->bot", photo_id=photo_id)
    else:
        await message.answer("❌ Отправь фото или напиши 'пропустить'.", reply_markup=keyboards.get_back_to_main_menu())
        return

    data = await state.get_data()
    seller_id = message.from_user.id
    try:
        product_id = db.add_product(seller_id, data)
        await message.answer(
            "✅ Товар или услуга отправлены на модерацию!",
            reply_markup=keyboards.get_main_menu()
        )
        await notify_admins(product_id, data, seller_id)
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при сохранении объявления для user_id={seller_id}: {e}")
        await message.answer("❌ Ошибка при сохранении объявления.")

# Обработчик показа карточки товара
@dp.callback_query(lambda c: c.data.startswith("product_"))
async def show_product(callback: types.CallbackQuery):
    """Отображение карточки товара или услуги."""
    try:
        product_id = int(callback.data.split("_")[1])
        product = db.get_product(product_id)
        if not product:
            logger.warning(f"Товар или услуга с ID {product_id} не найдены или не одобрены.")
            await callback.answer("❌ Товар или услуга не найдены.", show_alert=True)
            return
        name, price, description, photo, item_type = product
        type_label = "Товар" if item_type == "product" else "Услуга"
        caption = (
            f"{'📦' if item_type == 'product' else '🛠'} <b>{type_label}: {escape_html(name)}</b>\n"
            f"💸 Цена: {escape_html(price)}\n"
            f"✏️ {escape_html(description)}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Купить", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"buy_type_{item_type}")]
        ])
        try:
            if photo:
                await callback.message.edit_media(
                    media=types.InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"),
                    reply_markup=kb
                )
            else:
                await callback.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
            await callback.answer()
        except Exception as e:
            logger.error(f"Ошибка при отображении карточки товара product_id={product_id}: {e}")
            await callback.answer("❌ Ошибка при отображении.", show_alert=True)
    except ValueError as e:
        logger.error(f"Ошибка при разборе product_id в callback_data={callback.data}: {e}")
        await callback.answer("❌ Неверный формат ID товара.", show_alert=True)

# Обработчик одобрения товара
@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_product(callback: types.CallbackQuery):
    """Обработка одобрения товара/услуги администратором."""
    if callback.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к approve_product от user_id={callback.from_user.id}")
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    try:
        product_id = int(callback.data.split("_")[1])
        product = db.get_product_any_status(product_id)
        if not product:
            logger.warning(f"Товар или услуга с ID {product_id} не найдены в базе данных.")
            await callback.answer("❌ Товар или услуга не найдены.", show_alert=True)
            return
        name, price, description, photo, item_type = product
        seller_id = db.get_seller_id(product_id)
        if not seller_id:
            logger.warning(f"Продавец для товара с ID {product_id} не найден.")
            await callback.answer("❌ Продавец не найден.", show_alert=True)
            return
        # Проверяем текущий статус товара
        with sqlite3.connect("db.sqlite3") as conn:
            cur = conn.cursor()
            cur.execute("SELECT status FROM products WHERE id=?", (product_id,))
            current_status = cur.fetchone()
            if not current_status or current_status[0] != "pending":
                logger.warning(f"Товар с ID {product_id} имеет статус {current_status[0] if current_status else 'неизвестен'}, ожидается 'pending'.")
                await callback.answer(f"❌ Товар или услуга уже обработаны (статус: {current_status[0] if current_status else 'неизвестен'}).", show_alert=True)
                return
        type_label = "Товар" if item_type == "product" else "Услуга"
        caption = (
            f"🆔 {type_label} №{product_id}\n\n"
            f"{'📦' if item_type == 'product' else '🛠'} <b>{escape_html(name)}</b>\n"
            f"✏️ {escape_html(description)}\n"
            f"💸 Цена: {escape_html(price)}₽\n\n"
            f"<i>Бот для продажи и покупки товаров и услуг @SeIIStuff_bot</i>\n\n"
            f"<u>Чтобы купить, нажмите кнопку ниже. Или перейдите в бота @SeIIStuff_bot</u>"
        )
        kb_buy = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Купить", url=f"https://t.me/SeIIStuff_bot?start=product_{product_id}")]
        ])
        sent = None
        try:
            if photo:
                sent = await bot.send_photo(chat_id=Config.CHANNEL_ID, photo=photo, caption=caption, parse_mode="HTML", reply_markup=kb_buy)
            else:
                sent = await bot.send_message(chat_id=Config.CHANNEL_ID, text=caption, parse_mode="HTML", reply_markup=kb_buy)
            db.update_product_status(product_id, 'approved', channel_message_id=sent.message_id)
            await bot.send_message(
                seller_id,
                f"✅ Ваш {type_label.lower()} одобрен и опубликован в канале!",
                reply_markup=keyboards.get_main_menu()
            )
            old_caption = callback.message.caption or callback.message.text or ""
            if callback.message.photo:
                await callback.message.edit_caption(caption=f"{old_caption}\n\n✅ Одобрено", parse_mode="HTML")
            else:
                await callback.message.edit_text(f"{old_caption}\n\n✅ Одобрено", parse_mode="HTML")
            await callback.answer(f"{type_label} одобрен.")
        except Exception as e:
            logger.error(f"Ошибка при отправке в канал или обновлении статуса для product_id={product_id}: {e}")
            await callback.answer("❌ Ошибка при публикации в канал.", show_alert=True)
    except ValueError as e:
        logger.error(f"Ошибка при разборе product_id в callback_data={callback.data}: {e}")
        await callback.answer("❌ Неверный формат ID товара.", show_alert=True)
    except Exception as e:
        logger.error(f"Общая ошибка в approve_product для product_id={product_id}: {e}")
        await callback.answer("❌ Ошибка при одобрении.", show_alert=True)

# Обработчик отклонения товара
@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_product(callback: types.CallbackQuery):
    """Обработка отклонения товара/услуги администратором."""
    if callback.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к reject_product от user_id={callback.from_user.id}")
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    try:
        product_id = int(callback.data.split("_")[1])
        product = db.get_product_any_status(product_id)
        if not product:
            logger.warning(f"Товар или услуга с ID {product_id} не найдены в базе данных.")
            await callback.answer("❌ Товар или услуга не найдены.", show_alert=True)
            return
        name, _, _, _, item_type = product
        seller_id = db.get_seller_id(product_id)
        if not seller_id:
            logger.warning(f"Продавец для товара с ID {product_id} не найден.")
            await callback.answer("❌ Продавец не найден.", show_alert=True)
            return
        # Проверяем текущий статус товара
        with sqlite3.connect("db.sqlite3") as conn:
            cur = conn.cursor()
            cur.execute("SELECT status FROM products WHERE id=?", (product_id,))
            current_status = cur.fetchone()
            if not current_status or current_status[0] != "pending":
                logger.warning(f"Товар с ID {product_id} имеет статус {current_status[0] if current_status else 'неизвестен'}, ожидается 'pending'.")
                await callback.answer(f"❌ Товар или услуга уже обработаны (статус: {current_status[0] if current_status else 'неизвестен'}).", show_alert=True)
                return
        type_label = "Товар" if item_type == "product" else "Услуга"
        db.update_product_status(product_id, 'rejected')
        try:
            await bot.send_message(seller_id, f"❌ Ваш {type_label.lower()} '{escape_html(name)}' был отклонён модератором.")
            old_caption = callback.message.caption or callback.message.text or ""
            if callback.message.photo:
                await callback.message.edit_caption(caption=f"{old_caption}\n\n❌ Отклонено", parse_mode="HTML")
            else:
                await callback.message.edit_text(f"{old_caption}\n\n❌ Отклонено", parse_mode="HTML")
            await callback.answer(f"{type_label} отклонён.")
        except Exception as e:
            logger.error(f"Ошибка при уведомлении продавца или редактировании сообщения для product_id={product_id}: {e}")
            await callback.answer("❌ Ошибка при отклонении.", show_alert=True)
    except ValueError as e:
        logger.error(f"Ошибка при разборе product_id в callback_data={callback.data}: {e}")
        await callback.answer("❌ Неверный формат ID товара.", show_alert=True)
    except Exception as e:
        logger.error(f"Общая ошибка в reject_product для product_id={product_id}: {e}")
        await callback.answer("❌ Ошибка при отклонении.", show_alert=True)

# Обработчик начала чата
@dp.callback_query(lambda c: c.data.startswith("buy_") and c.data != "buy_select_type")
async def start_chat(callback: types.CallbackQuery, state: FSMContext):
    """Начало чата между покупателем и продавцом."""
    try:
        product_id = int(callback.data.split("_")[1])
        buyer_id = callback.from_user.id
        product = db.get_product(product_id)
        if not product or product[4] not in ["product", "service"]:
            logger.warning(f"Товар или услуга с ID {product_id} не найдены или не одобрены.")
            await callback.answer("❌ Товар или услуга не найдены или недоступны.", show_alert=True)
            return
        seller_id = db.get_seller_id(product_id)
        name, _, _, _, item_type = product
        type_label = "товару" if item_type == "product" else "услуге"
        order_id = db.create_order(product_id, seller_id, buyer_id)
        kb_finish_seller = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Завершить сделку (продавец)", callback_data=f"finish_seller_{order_id}")],
            [InlineKeyboardButton(text="❌ Отменить сделку", callback_data=f"cancel_{order_id}")]
        ])
        sent_seller = await bot.send_message(
            seller_id,
            f"🔥 Новый покупатель по {type_label} №{product_id} ({escape_html(name)}).\n\nПишите сюда, а бот всё пересылает.",
            reply_markup=kb_finish_seller
        )
        db.update_order_message_id(order_id, seller_message_id=sent_seller.message_id)
        kb_finish_buyer = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Завершить сделку (покупатель)", callback_data=f"finish_buyer_{order_id}")],
            [InlineKeyboardButton(text="❌ Отменить сделку", callback_data=f"cancel_{order_id}")]
        ])
        sent_buyer = await bot.send_message(
            buyer_id,
            f"💬 Вы начали чат с продавцом по {type_label} №{product_id} ({escape_html(name)}).\n\n"
            f"Когда {type_label} получен(а) и всё в порядке, нажмите кнопку ниже:",
            reply_markup=kb_finish_buyer
        )
        db.update_order_message_id(order_id, buyer_message_id=sent_buyer.message_id)
        await state.update_data(order_id=order_id)
        await state.set_state(Chatting.chatting_buyer)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в start_chat для product_id={product_id}: {e}")
        await callback.answer("❌ Ошибка при начале чата.", show_alert=True)

# Обработчик пересылки сообщений в чате
@dp.message(lambda message: message.text is None or (message.text and not message.text.startswith('/')))
async def relay_message(message: types.Message, state: FSMContext):
    """Пересылка сообщений между покупателем и продавцом в активной сделке."""
    user_id = message.from_user.id
    try:
        order = db.get_active_order_by_user(user_id)
        if not order:
            if message.text:
                log_user_message(user_id, "user", "->bot", text=message.text)
            elif message.photo:
                log_user_message(user_id, "user", "->bot", photo_id=message.photo[-1].file_id)
            await message.answer("❌ У вас нет активных сделок.")
            return
        product_id, seller_id, buyer_id = order
        product = db.get_product(product_id)
        if not product:
            logger.warning(f"Товар или услуга с ID {product_id} не найдены для заказа.")
            await message.answer("❌ Товар или услуга не найдены.")
            return
        name, _, _, _, item_type = product
        type_label = "покупателя" if item_type == "product" else "заказчика" if user_id == buyer_id else "продавца" if item_type == "product" else "исполнителя"
        target_id = seller_id if user_id == buyer_id else buyer_id
        if message.text:
            await bot.send_message(target_id, f"📩 От {type_label}: {message.text}")
            log_user_message(user_id, "buyer" if user_id == buyer_id else "seller", f"->{'seller' if user_id == buyer_id else 'buyer'}", text=message.text)
        elif message.photo:
            await bot.send_photo(target_id, message.photo[-1].file_id, caption=f"📸 Фото от {type_label}")
            log_user_message(user_id, "buyer" if user_id == buyer_id else "seller", f"->{'seller' if user_id == buyer_id else 'buyer'}", photo_id=message.photo[-1].file_id)
    except Exception as e:
        logger.error(f"Ошибка в relay_message для user_id={user_id}: {e}")
        await message.answer("❌ Ошибка при обработке сообщения.")

# Обработчик подтверждения сделки продавцом
@dp.callback_query(lambda c: c.data.startswith("finish_seller_"))
async def finish_seller(callback: types.CallbackQuery):
    """Подтверждение сделки продавцом."""
    try:
        order_id = int(callback.data.split("_")[2])
        result = db.confirm_order(order_id, "seller")
        if not result:
            logger.warning(f"Заказ с ID {order_id} не найден.")
            await callback.answer("❌ Заказ не найден.", show_alert=True)
            return
        seller_conf, buyer_conf, product_id, seller_id, buyer_id = result
        if buyer_conf:
            await complete_order(order_id, product_id, seller_id, buyer_id)
        else:
            await callback.answer("Вы подтвердили сделку. Ждём подтверждения от покупателя.")
    except Exception as e:
        logger.error(f"Ошибка в finish_seller для order_id={order_id}: {e}")
        await callback.answer("❌ Ошибка при подтверждении сделки.", show_alert=True)

# Обработчик подтверждения сделки покупателем
@dp.callback_query(lambda c: c.data.startswith("finish_buyer_"))
async def finish_buyer(callback: types.CallbackQuery):
    """Подтверждение сделки покупателем."""
    try:
        order_id = int(callback.data.split("_")[2])
        result = db.confirm_order(order_id, "buyer")
        if not result:
            logger.warning(f"Заказ с ID {order_id} не найден.")
            await callback.answer("❌ Заказ не найден.", show_alert=True)
            return
        seller_conf, buyer_conf, product_id, seller_id, buyer_id = result
        if seller_conf:
            await complete_order(order_id, product_id, seller_id, buyer_id)
        else:
            await callback.answer("Вы подтвердили сделку. Ждём подтверждения от продавца.")
    except Exception as e:
        logger.error(f"Ошибка в finish_buyer для order_id={order_id}: {e}")
        await callback.answer("❌ Ошибка при подтверждении сделки.", show_alert=True)

async def complete_order(order_id: int, product_id: int, seller_id: int, buyer_id: int):
    """Завершение сделки после подтверждения обеих сторон."""
    try:
        product = db.get_product(product_id)
        if not product:
            logger.warning(f"Товар или услуга с ID {product_id} не найдены для завершения заказа.")
            return
        name, price, description, photo, item_type = product
        type_label = "Товар" if item_type == "product" else "Услуга"
        db.update_order_status(order_id, "completed")
        db.update_product_status(product_id, "sold")
        channel_message_id = db.get_channel_message_id(product_id)
        if channel_message_id:
            crossed_caption = (
                f"<s>{'📦' if item_type == 'product' else '🛠'} <b>{type_label}: {escape_html(name)}</b>\n"
                f"💸 Цена: {escape_html(price)}\n"
                f"✏️ {escape_html(description)}</s>\n\n"
                f"<b>✅ ПРОДАНО</b>"
            )
            try:
                if photo:
                    await bot.edit_message_caption(
                        chat_id=Config.CHANNEL_ID,
                        message_id=channel_message_id,
                        caption=crossed_caption,
                        parse_mode="HTML",
                        reply_markup=None
                    )
                else:
                    await bot.edit_message_text(
                        chat_id=Config.CHANNEL_ID,
                        message_id=channel_message_id,
                        text=crossed_caption,
                        parse_mode="HTML",
                        reply_markup=None
                    )
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения в канале для product_id={product_id}: {e}")
        buyer_msg_id, seller_msg_id = db.get_order_message_ids(order_id)
        if buyer_msg_id:
            try:
                await bot.delete_message(buyer_id, buyer_msg_id)
            except Exception as e:
                logger.warning(f"Ошибка удаления сообщения у покупателя {buyer_id}: {e}")
        if seller_msg_id:
            try:
                await bot.delete_message(seller_id, seller_msg_id)
            except Exception as e:
                logger.warning(f"Ошибка удаления сообщения у продавца {seller_id}: {e}")
        await bot.send_message(seller_id, f"✅ Сделка по {type_label.lower()} №{product_id} завершена обеими сторонами.")
        await bot.send_message(buyer_id, f"✅ Сделка по {type_label.lower()} №{product_id} завершена обеими сторонами.")
    except Exception as e:
        logger.error(f"Ошибка в complete_order для order_id={order_id}: {e}")

# Обработчик отмены сделки
@dp.callback_query(lambda c: c.data.startswith("cancel_"))
async def cancel_order(callback: types.CallbackQuery):
    """Отмена сделки покупателем или продавцом."""
    try:
        order_id = int(callback.data.split("_")[1])
        order = db.get_order(order_id)
        if not order:
            logger.warning(f"Заказ с ID {order_id} не найден.")
            await callback.answer("❌ Заказ не найден.", show_alert=True)
            return
        if order[4] != "in_progress":
            logger.warning(f"Заказ с ID {order_id} уже имеет статус {order[4]}.")
            await callback.answer("⚠️ Этот заказ уже закрыт.", show_alert=True)
            return
        product_id, seller_id, buyer_id, _, _ = order
        product = db.get_product(product_id)
        type_label = "Товар" if product[4] == "product" else "Услуга"
        db.update_order_status(order_id, "canceled")
        buyer_msg_id, seller_msg_id = db.get_order_message_ids(order_id)
        kb = keyboards.get_main_menu()
        if buyer_msg_id:
            await bot.send_message(buyer_id, f"❌ Сделка по {type_label.lower()} №{order_id} отменена.", reply_markup=kb)
        if seller_msg_id:
            await bot.send_message(seller_id, f"❌ Сделка по {type_label.lower()} №{order_id} отменена.", reply_markup=kb)
        if buyer_msg_id:
            try:
                await bot.delete_message(buyer_id, buyer_msg_id)
            except Exception as e:
                logger.warning(f"Ошибка удаления сообщения у покупателя {buyer_id}: {e}")
        if seller_msg_id:
            try:
                await bot.delete_message(seller_id, seller_msg_id)
            except Exception as e:
                logger.warning(f"Ошибка удаления сообщения у продавца {seller_id}: {e}")
        await callback.answer(f"Сделка по {type_label.lower()} №{order_id} отменена.")
    except Exception as e:
        logger.error(f"Ошибка в cancel_order для order_id={order_id}: {e}")
        await callback.answer("❌ Ошибка при отмене сделки.", show_alert=True)

# Обработчик команды /pending
@dp.message(Command(commands=["pending"]))
async def show_pending(message: types.Message):
    """Отображение списка товаров/услуг на модерации."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /pending от user_id={message.from_user.id}")
        return
    try:
        products = db.get_pending_products()
        if not products:
            await message.answer("✅ Нет товаров или услуг на модерации.")
            return
        for product_id, name, price, item_type in products:
            product = db.get_product_any_status(product_id)
            if not product:
                continue
            name, price, description, photo, item_type = product
            type_label = "Товар" if item_type == "product" else "Услуга"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{product_id}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{product_id}")
                ]
            ])
            caption = (
                f"🆔 {type_label} №{product_id}\n\n"
                f"{'📦' if item_type == 'product' else '🛠'} <b>{escape_html(name)}</b>\n"
                f"✏️ {escape_html(description)}\n"
                f"💸 Цена: {escape_html(price)}₽"
            )
            if photo:
                await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML", reply_markup=kb)
            else:
                await message.answer(caption, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка в show_pending для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при получении списка.")

# Обработчик команды /approved
@dp.message(Command(commands=["approved"]))
async def show_approved(message: types.Message):
    """Отображение списка активных товаров/услуг."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /approved от user_id={message.from_user.id}")
        return
    try:
        products = db.get_approved_products()
        if not products:
            await message.answer("🤷‍♂️ Нет активных товаров или услуг.")
            return
        for product_id, name, price, item_type in products:
            name = escape_html(name)
            price = escape_html(price)
            type_label = "Товар" if item_type == "product" else "Услуга"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_product_{product_id}")]
            ])
            await message.answer(f"{'📦' if item_type == 'product' else '🛠'} {type_label} #{product_id} {name} — {price}₽", reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка в show_approved для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при получении списка.")

# Обработчик команды /reject
@dp.message(Command(commands=["reject"]))
async def show_rejected(message: types.Message):
    """Отображение списка отклоненных товаров/услуг."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /reject от user_id={message.from_user.id}")
        return
    try:
        products = db.get_rejected_products()
        if not products:
            await message.answer("❌ Нет отклонённых товаров или услуг.")
            return
        text = "📄 Список отклонённых товаров и услуг:\n"
        for product_id, name, price, item_type in products:
            name = escape_html(name)
            price = escape_html(price)
            type_label = "Товар" if item_type == "product" else "Услуга"
            text += f"{'📦' if item_type == 'product' else '🛠'} {type_label} #{product_id} — {name} — {price}₽\n"
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в show_rejected для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при получении списка.")

# Обработчик команды /delete
@dp.message(Command(commands=["delete"]))
async def delete_item(message: types.Message):
    """Удаление товара/услуги или рекламного поста."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /delete от user_id={message.from_user.id}")
        return
    try:
        args = message.text.split()
        if len(args) != 3 or args[1] not in ["adv", "post"]:
            await message.answer("⚠️ Использование: /delete <adv/post> <id>")
            return
        item_type, item_id = args[1], int(args[2])
        if item_type == "post":
            product = db.get_product_any_status(item_id)
            if not product:
                logger.warning(f"Товар или услуга с ID {item_id} не найдены для удаления.")
                await message.answer(f"❌ Товар или услуга с ID {item_id} не найдена.")
                return
            channel_msg_id, item_type = db.get_channel_message_id(item_id), product[4]
            type_label = "Товар" if item_type == "product" else "Услуга"
            if channel_msg_id:
                try:
                    await bot.delete_message(Config.CHANNEL_ID, channel_msg_id)
                except Exception as e:
                    logger.warning(f"Ошибка удаления сообщения в канале для product_id={item_id}: {e}")
                    await message.answer(f"⚠️ Не удалось удалить сообщение в канале: {e}")
            db.delete_product(item_id)
            await message.answer(f"🗑 {type_label} #{item_id} удалён.")
        elif item_type == "adv":
            ad = db.get_ad(item_id)
            if not ad:
                logger.warning(f"Рекламный пост с ID {item_id} не найден.")
                await message.answer(f"❌ Рекламный пост с ID {item_id} не найден.")
                return
            channel_msg_id = db.get_ad_channel_message_id(item_id)
            if channel_msg_id:
                try:
                    await bot.delete_message(Config.CHANNEL_ID, channel_msg_id)
                    await message.answer(f"🗑 Сообщение рекламного поста #{item_id} удалено из канала.")
                except Exception as e:
                    logger.warning(f"Ошибка удаления сообщения в канале для ad_id={item_id}: {e}")
                    await message.answer(f"⚠️ Не удалось удалить сообщение в канале: {e}")
            db.delete_ad(item_id)
            await message.answer(f"🗑 Рекламный пост #{item_id} удалён.")
    except Exception as e:
        logger.error(f"Ошибка в delete_item для item_type={item_type} item_id={item_id}: {e}")
        await message.answer("❌ Ошибка при удалении.")

# Обработчик команды /broadcast
@dp.message(Command(commands=["broadcast"]))
async def broadcast(message: types.Message):
    """Рассылка сообщения всем пользователям."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /broadcast от user_id={message.from_user.id}")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Напиши текст рассылки: /broadcast <текст>")
        return
    text = args[1]
    users = db.get_all_users()
    sent = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception as e:
            logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
    await message.answer(f"✅ Сообщение отправлено {sent} пользователям.")

# Обработчик команды /orders
@dp.message(Command(commands=["orders"]))
async def cmd_orders(message: types.Message):
    """Отображение списка активных сделок."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /orders от user_id={message.from_user.id}")
        return
    try:
        orders = db.get_active_orders()
        if not orders:
            await message.answer("🛒 Активных сделок нет.")
            return
        text_lines = ["📋 <b>Активные сделки:</b>\n"]
        for order_id, product_id, seller_id, buyer_id, status in orders:
            product = db.get_product(product_id)
            type_label = "Товар" if product[4] == "product" else "Услуга"
            text_lines.append(
                f"🆔 {order_id} | {type_label} #{product_id}\n👤 Продавец: {seller_id}\n🧑‍💻 Покупатель: {buyer_id}\nСтатус: {status}\n"
            )
        await message.answer("\n".join(text_lines), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в cmd_orders для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при получении списка сделок.")

# Обработчик команды /close_order
@dp.message(Command(commands=["close_order"]))
async def cmd_close_order(message: types.Message):
    """Принудительное завершение сделки администратором."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /close_order от user_id={message.from_user.id}")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Использование: /close_order <id>")
        return
    try:
        order_id = int(args[1])
        order = db.get_order(order_id)
        if not order:
            logger.warning(f"Заказ с ID {order_id} не найден.")
            await message.answer("❌ Заказ не найден.")
            return
        product_id, seller_id, buyer_id, _, _ = order
        product = db.get_product(product_id)
        type_label = "Товар" if product[4] == "product" else "Услуга"
        db.update_order_status(order_id, "completed")
        db.update_product_status(product_id, "sold")
        await bot.send_message(seller_id, f"✅ Сделка по {type_label.lower()} #{order_id} была завершена администратором.")
        await bot.send_message(buyer_id, f"✅ Сделка по {type_label.lower()} #{order_id} была завершена администратором.")
        await message.answer(f"✅ Сделка по {type_label.lower()} #{order_id} закрыта.")
    except Exception as e:
        logger.error(f"Ошибка в cmd_close_order для order_id={order_id}: {e}")
        await message.answer("❌ Ошибка при закрытии сделки.")

# Обработчик команды /cancel_order
@dp.message(Command(commands=["cancel_order"]))
async def cmd_cancel_order(message: types.Message):
    """Принудительная отмена сделки администратором."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /cancel_order от user_id={message.from_user.id}")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Использование: /cancel_order <id>")
        return
    try:
        order_id = int(args[1])
        order = db.get_order(order_id)
        if not order:
            logger.warning(f"Заказ с ID {order_id} не найден.")
            await message.answer("❌ Заказ не найден.")
            return
        product_id, seller_id, buyer_id, _, _ = order
        product = db.get_product(product_id)
        type_label = "Товар" if product[4] == "product" else "Услуга"
        db.update_order_status(order_id, "canceled")
        await bot.send_message(seller_id, f"❌ Сделка по {type_label.lower()} #{order_id} отменена администратором.")
        await bot.send_message(buyer_id, f"❌ Сделка по {type_label.lower()} #{order_id} отменена администратором.")
        await message.answer(f"❌ Сделка по {type_label.lower()} #{order_id} отменена.")
    except Exception as e:
        logger.error(f"Ошибка в cmd_cancel_order для order_id={order_id}: {e}")
        await message.answer("❌ Ошибка при отмене сделки.")

# Обработчик команды /stats
@dp.message(Command(commands=["stats"]))
async def cmd_stats(message: types.Message):
    """Отображение статистики бота."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /stats от user_id={message.from_user.id}")
        return
    try:
        total_products, active_products, sold_products, total_users = db.get_stats()
        stats_text = (
            f"📊 <b>Статистика:</b>\n"
            f"Всего товаров и услуг: {total_products}\n"
            f"Активных: {active_products}\n"
            f"Продано: {sold_products}\n"
            f"Пользователей: {total_users}\n"
        )
        await message.answer(stats_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в cmd_stats для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при получении статистики.")

# Обработчик команды /user
@dp.message(Command(commands=["user"]))
async def cmd_user_info(message: types.Message):
    """Отображение информации о пользователе."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /user от user_id={message.from_user.id}")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Использование: /user <user_id>")
        return
    try:
        user_id = int(args[1])
        products_count, sold_count, bought_count = db.get_user_info(user_id)
        info = (
            f"👤 <b>Пользователь {user_id}</b>\n"
            f"Выставил товаров/услуг: {products_count}\n"
            f"Продал: {sold_count}\n"
            f"Купил: {bought_count}\n"
        )
        await message.answer(info, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в cmd_user_info для user_id={user_id}: {e}")
        await message.answer("❌ Ошибка при получении информации.")

# Обработчик команды /logs
@dp.message(Command(commands=["logs"]))
async def cmd_logs(message: types.Message, state: FSMContext):
    """Отображение списка папок с логами."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /logs от user_id={message.from_user.id}")
        return
    try:
        folders = keyboards.get_date_folders()
        if not folders:
            await message.answer("❌ Лог-папки не найдены.")
            return
        await message.answer("📅 Выберите папку с логами:", reply_markup=keyboards.build_logs_kb(0))
        await state.set_state(LogsState.select_folder)
    except Exception as e:
        logger.error(f"Ошибка в cmd_logs для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при получении логов.")

# Обработчик пагинации логов
@dp.callback_query(F.data.startswith("logs_page:"))
async def paginate_logs(callback: types.CallbackQuery):
    """Переключение страниц с папками логов."""
    try:
        page = int(callback.data.split(":")[1])
        await callback.message.edit_reply_markup(reply_markup=keyboards.build_logs_kb(page))
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в paginate_logs для callback_data={callback.data}: {e}")
        await callback.answer("❌ Ошибка при переключении страницы логов.", show_alert=True)

# Обработчик открытия папки логов
@dp.callback_query(F.data.startswith("logs_open:"))
async def open_logs_folder(callback: types.CallbackQuery, state: FSMContext):
    """Отправка файлов логов из выбранной папки."""
    if callback.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к logs_open от user_id={callback.from_user.id}")
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    try:
        folder = callback.data.split(":")[1]
        folder_path = os.path.join(Config.LOGS_BASE_DIR, folder)
        if not os.path.exists(folder_path):
            logger.warning(f"Папка логов {folder_path} не найдена.")
            await callback.answer("❌ Папка не найдена.", show_alert=True)
            return
        log_files = [f for f in os.listdir(folder_path) if f.endswith(".log")]
        if not log_files:
            logger.info(f"Папка {folder_path} пуста.")
            await callback.answer("📂 Папка пуста.", show_alert=True)
            return
        for log_file in log_files:
            file_path = os.path.join(folder_path, log_file)
            try:
                await bot.send_document(
                    chat_id=callback.from_user.id,
                    document=FSInputFile(file_path),
                    caption=f"Лог-файл: {log_file}"
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке файла {file_path}: {e}")
                await callback.message.answer(f"❌ Не удалось отправить файл {log_file}.")
        await callback.message.edit_text("📂 Логи отправлены.", reply_markup=keyboards.get_main_menu())
        await state.clear()
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в open_logs_folder для folder={folder}: {e}")
        await callback.answer("❌ Ошибка при открытии папки логов.", show_alert=True)

# Обработчик команды /db_backup
@dp.message(Command(commands=["db_backup"]))
async def cmd_db_backup(message: types.Message):
    """Создание и отправка бэкапа базы данных."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /db_backup от user_id={message.from_user.id}")
        return
    try:
        import shutil
        from datetime import datetime
        backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
        shutil.copyfile("db.sqlite3", backup_path)
        await bot.send_document(
            chat_id=message.from_user.id,
            document=FSInputFile(backup_path),
            caption="📦 Бэкап базы данных"
        )
        os.remove(backup_path)
        await message.answer("✅ Бэкап отправлен.")
    except Exception as e:
        logger.error(f"Ошибка в cmd_db_backup для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при создании бэкапа.")

# Обработчик команды /ban
@dp.message(Command(commands=["ban"]))
async def cmd_ban_user(message: types.Message):
    """Запрет пользователю продавать."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /ban от user_id={message.from_user.id}")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Использование: /ban <user_id>")
        return
    try:
        user_id = int(args[1])
        db.ban_user(user_id)
        await message.answer(f"🚫 Пользователь {user_id} заблокирован для продаж.")
        await bot.send_message(user_id, "🚫 Вам запрещено продавать товары и услуги.")
    except Exception as e:
        logger.error(f"Ошибка в cmd_ban_user для user_id={user_id}: {e}")
        await message.answer("❌ Ошибка при блокировке пользователя.")

# Обработчик команды /unban
@dp.message(Command(commands=["unban"]))
async def cmd_unban_user(message: types.Message):
    """Снятие запрета на продажу для пользователя."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /unban от user_id={message.from_user.id}")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Использование: /unban <user_id>")
        return
    try:
        user_id = int(args[1])
        db.unban_user(user_id)
        await message.answer(f"✅ Пользователь {user_id} разблокирован для продаж.")
        await bot.send_message(user_id, "✅ Вам разрешено продавать товары и услуги.")
    except Exception as e:
        logger.error(f"Ошибка в cmd_unban_user для user_id={user_id}: {e}")
        await message.answer("❌ Ошибка при разблокировке пользователя.")

# Обработчик команды /sellers
@dp.message(Command(commands=["sellers"]))
async def cmd_top_sellers(message: types.Message):
    """Отображение топ-10 продавцов по количеству продаж."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /sellers от user_id={message.from_user.id}")
        return
    try:
        sellers = db.get_top_sellers()
        if not sellers:
            await message.answer("📉 Нет данных о продавцах.")
            return
        text = "🏆 <b>Топ-10 продавцов:</b>\n"
        for i, (seller_id, sales) in enumerate(sellers, 1):
            text += f"{i}. Пользователь {seller_id} — {sales} продаж\n"
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в cmd_top_sellers для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при получении топа продавцов.")

# Обработчик команды /buyers
@dp.message(Command(commands=["buyers"]))
async def cmd_top_buyers(message: types.Message):
    """Отображение топ-10 покупателей по количеству покупок."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /buyers от user_id={message.from_user.id}")
        return
    try:
        buyers = db.get_top_buyers()
        if not buyers:
            await message.answer("📉 Нет данных о покупателях.")
            return
        text = "🏆 <b>Топ-10 покупателей:</b>\n"
        for i, (buyer_id, purchases) in enumerate(buyers, 1):
            text += f"{i}. Пользователь {buyer_id} — {purchases} покупок\n"
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в cmd_top_buyers для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при получении топа покупателей.")

# Обработчик команды /send_user
@dp.message(Command(commands=["send_user"]))
async def cmd_send_user(message: types.Message):
    """Отправка личного сообщения пользователю от имени администратора."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /send_user от user_id={message.from_user.id}")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⚠️ Использование: /send_user <user_id> <текст>")
        return
    try:
        user_id = int(args[1])
        text = args[2]
        await bot.send_message(user_id, f"📩 Сообщение от администратора:\n{text}")
        await message.answer(f"✅ Сообщение отправлено пользователю {user_id}.")
    except Exception as e:
        logger.error(f"Ошибка в cmd_send_user для user_id={user_id}: {e}")
        await message.answer("❌ Ошибка при отправке сообщения.")

# Обработчик команды /pin
@dp.message(Command(commands=["pin"]))
async def cmd_pin(message: types.Message):
    """Закрепление сообщения товара или услуги в канале."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /pin от user_id={message.from_user.id}")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Использование: /pin <id>")
        return
    try:
        product_id = int(args[1])
        channel_message_id = db.get_channel_message_id(product_id)
        if not channel_message_id:
            logger.warning(f"Сообщение в канале для product_id={product_id} не найдено.")
            await message.answer("❌ Сообщение в канале не найдено.")
            return
        product = db.get_product(product_id)
        if not product:
            logger.warning(f"Товар или услуга с ID {product_id} не найдены или не одобрены.")
            await message.answer("❌ Товар или услуга не найдены.")
            return
        type_label = "Товар" if product[4] == "product" else "Услуга"
        await bot.pin_chat_message(chat_id=Config.CHANNEL_ID, message_id=channel_message_id)
        await message.answer(f"📌 {type_label} #{product_id} закреплён в канале.")
    except Exception as e:
        logger.error(f"Ошибка в cmd_pin для product_id={product_id}: {e}")
        await message.answer("❌ Ошибка при закреплении сообщения.")

# Обработчик команды /unpin
@dp.message(Command(commands=["unpin"]))
async def cmd_unpin(message: types.Message):
    """Открепление всех сообщений в канале."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /unpin от user_id={message.from_user.id}")
        return
    try:
        await bot.unpin_all_chat_messages(chat_id=Config.CHANNEL_ID)
        await message.answer("📌 Все сообщения откреплены в канале.")
    except Exception as e:
        logger.error(f"Ошибка в cmd_unpin для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при откреплении сообщений.")

# Обработчик команды /adv
@dp.message(Command(commands=["adv"]))
async def cmd_create_ad(message: types.Message, state: FSMContext):
    """Создание нового рекламного поста."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /adv от user_id={message.from_user.id}")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Напиши текст рекламы: /adv <текст>")
        return
    try:
        text = args[1]
        ad_id = db.create_ad(text, None)
        await message.answer(f"📢 Рекламный пост #{ad_id} создан. Отправить: /send_adv {ad_id} <all/channel>")
    except Exception as e:
        logger.error(f"Ошибка в cmd_create_ad для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при создании рекламного поста.")

# Обработчик команды /send_adv
@dp.message(Command(commands=["send_adv"]))
async def cmd_send_ad(message: types.Message):
    """Отправка рекламного поста в канал или всем пользователям."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /send_adv от user_id={message.from_user.id}")
        return
    args = message.text.split()
    if len(args) != 3 or args[2] not in ["all", "channel"]:
        await message.answer("⚠️ Использование: /send_adv <id_поста> <all/channel>")
        return
    try:
        ad_id = int(args[1])
        target = args[2]
        ad = db.get_ad(ad_id)
        if not ad:
            logger.warning(f"Рекламный пост с ID {ad_id} не найден.")
            await message.answer(f"❌ Рекламный пост #{ad_id} не найден.")
            return
        text, photo = ad
        if target == "channel":
            sent = None
            try:
                if photo:
                    sent = await bot.send_photo(chat_id=Config.CHANNEL_ID, photo=photo, caption=text, parse_mode="HTML")
                else:
                    sent = await bot.send_message(chat_id=Config.CHANNEL_ID, text=text, parse_mode="HTML")
                db.update_ad_channel_message_id(ad_id, sent.message_id)
                await message.answer(f"📢 Рекламный пост #{ad_id} отправлен в канал.")
            except Exception as e:
                logger.error(f"Ошибка при отправке рекламы в канал для ad_id={ad_id}: {e}")
                await message.answer("❌ Ошибка при отправке в канал.")
        else:  # all
            users = db.get_all_users()
            sent = 0
            for user_id in users:
                try:
                    if photo:
                        await bot.send_photo(user_id, photo, caption=text, parse_mode="HTML")
                    else:
                        await bot.send_message(user_id, text, parse_mode="HTML")
                    sent += 1
                except Exception as e:
                    logger.warning(f"Не удалось отправить рекламу пользователю {user_id}: {e}")
            await message.answer(f"✅ Рекламный пост #{ad_id} отправлен {sent} пользователям.")
    except Exception as e:
        logger.error(f"Ошибка в cmd_send_ad для ad_id={ad_id}: {e}")
        await message.answer("❌ Ошибка при отправке рекламного поста.")

# Обработчик команды /admins
@dp.message(Command(commands=["admins"]))
async def cmd_list_admins(message: types.Message):
    """Отображение списка текущих администраторов."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /admins от user_id={message.from_user.id}")
        return
    try:
        admins = Config.ADMINS
        if not admins:
            await message.answer("🤷‍♂️ Список администраторов пуст.")
            return
        text = "👑 <b>Список администраторов:</b>\n"
        for admin_id in admins:
            text += f"Пользователь {admin_id}\n"
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в cmd_list_admins для user_id={message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при получении списка администраторов.")

# Обработчик команды /add_admin
@dp.message(Command(commands=["add_admin"]))
async def cmd_add_admin(message: types.Message):
    """Добавление нового администратора."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /add_admin от user_id={message.from_user.id}")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Использование: /add_admin <user_id>")
        return
    try:
        user_id = int(args[1])
        if user_id in Config.ADMINS:
            await message.answer(f"⚠️ Пользователь {user_id} уже является администратором.")
            return
        Config.ADMINS.append(user_id)
        await message.answer(f"✅ Пользователь {user_id} добавлен в администраторы.")
        await bot.send_message(user_id, "👑 Вы назначены администратором бота!")
    except Exception as e:
        logger.error(f"Ошибка в cmd_add_admin для user_id={user_id}: {e}")
        await message.answer("❌ Ошибка при добавлении администратора.")

# Обработчик команды /remove_admin
@dp.message(Command(commands=["remove_admin"]))
async def cmd_remove_admin(message: types.Message):
    """Удаление администратора."""
    if message.from_user.id not in Config.ADMINS:
        logger.warning(f"Несанкционированный доступ к /remove_admin от user_id={message.from_user.id}")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Использование: /remove_admin <user_id>")
        return
    try:
        user_id = int(args[1])
        if user_id not in Config.ADMINS:
            await message.answer(f"⚠️ Пользователь {user_id} не является администратором.")
            return
        Config.ADMINS.remove(user_id)
        await message.answer(f"✅ Пользователь {user_id} удалён из администраторов.")
        await bot.send_message(user_id, "🚫 Вы больше не администратор бота.")
    except Exception as e:
        logger.error(f"Ошибка в cmd_remove_admin для user_id={user_id}: {e}")
        await message.answer("❌ Ошибка при удалении администратора.")

async def show_product_card(message: types.Message, product_id: int):
    """Отображение карточки товара или услуги по ID."""
    try:
        product = db.get_product(product_id)
        if not product:
            logger.warning(f"Товар или услуга с ID {product_id} не найдены или не одобрены.")
            await message.answer("❌ Товар или услуга не найдены.")
            return
        name, price, description, photo, item_type = product
        type_label = "Товар" if item_type == "product" else "Услуга"
        caption = (
            f"{'📦' if item_type == 'product' else '🛠'} <b>{type_label}: {escape_html(name)}</b>\n"
            f"💸 Цена: {escape_html(price)}\n"
            f"✏️ {escape_html(description)}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Купить", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"buy_type_{item_type}")]
        ])
        if photo:
            await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML", reply_markup=kb)
        else:
            await message.answer(caption, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка в show_product_card для product_id={product_id}: {e}")
        await message.answer("❌ Ошибка при отображении карточки товара.")

async def notify_admins(product_id: int, data: dict, seller_id: int):
    """Уведомление администраторов о новом товаре/услуге на модерации."""
    try:
        type_label = "Товар" if data["type"] == "product" else "Услуга"
        caption = (
            f"🆕 {type_label} №{product_id} от пользователя {seller_id}\n\n"
            f"{'📦' if data['type'] == 'product' else '🛠'} <b>{escape_html(data['name'])}</b>\n"
            f"✏️ {escape_html(data['description'])}\n"
            f"💸 Цена: {escape_html(data['price'])}₽\n"
            f"📱 Контакт: {escape_html(data['contact'])}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{product_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{product_id}")
            ]
        ])
        for admin_id in Config.ADMINS:
            try:
                if data.get("photo"):
                    await bot.send_photo(
                        chat_id=admin_id,
                        photo=data["photo"],
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=kb
                    )
                else:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=caption,
                        parse_mode="HTML",
                        reply_markup=kb
                    )
            except Exception as e:
                logger.warning(f"Не удалось уведомить админа {admin_id} о product_id={product_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка в notify_admins для product_id={product_id}: {e}")

async def main():
    """Запуск бота."""
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())