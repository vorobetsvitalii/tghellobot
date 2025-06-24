# 1. Базовий образ з Python
FROM python:3.11-slim

# 2. Робоча директорія
WORKDIR /app

# 3. Копіюємо файл із залежностями й встановлюємо їх
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Копіюємо всі файли проєкту
COPY . .

# 5. Запускаємо бота
CMD ["python", "main2.py"]
