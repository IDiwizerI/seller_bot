from aiogram.fsm.state import State, StatesGroup

class SellProduct(StatesGroup):
    """Состояния для процесса добавления товара/услуги."""
    type = State()
    name = State()
    description = State()
    price = State()
    contact = State()
    photo = State()

class Chatting(StatesGroup):
    """Состояния для чата между покупателем и продавцом."""
    chatting_buyer = State()

class LogsState(StatesGroup):
    """Состояния для просмотра логов."""
    waiting_for_date = State()