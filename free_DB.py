import sqlite3

# Путь к твоей БД
DB_PATH = "db.sqlite3"

# Подключаемся
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Список таблиц, которые хочешь очистить
tables_to_clear = ["products", "orders", "users", "ads"]

for table in tables_to_clear:
    cur.execute(f"DELETE FROM {table};")  # Удаляем все строки
    cur.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}';")  # Сбрасываем автоинкремент (id начнется с 1)

conn.commit()
conn.close()

print("✅ Все данные удалены и счетчики сброшены!")
