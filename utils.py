import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def escape_html(text: str) -> str:
    """Экранирование HTML-символов в тексте."""
    if not text:
        return text
    return text.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')

def log_user_message(user_id: int, role: str, direction: str, text: str = None, photo_id: str = None) -> None:
    """Логирование сообщений пользователей."""
    try:
        date_folder = datetime.now().strftime("%Y-%m-%d")
        folder_path = os.path.join("logs", date_folder)
        os.makedirs(folder_path, exist_ok=True)
        file_path = os.path.join(folder_path, f"{user_id}.log")
        time_now = datetime.now().strftime("%H:%M:%S")
        msg = f"[{time_now}] ({role}) {direction} {'PHOTO: ' + photo_id if photo_id else 'TEXT: ' + (text or '')}\n"
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(msg)
    except Exception as e:
        logger.error(f"Ошибка логирования для user_id={user_id}: {e}")