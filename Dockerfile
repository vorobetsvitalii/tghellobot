# 1. Базовий образ з Python
FROM python:3.11-slim

# 2. Робоча директорія
WORKDIR /app

# 3. Встановлюємо залежність
RUN pip install --no-cache-dir python-telegram-bot==20.6

# 4. Копіюємо весь ваш код і конфіги
COPY . .

# 5. Запускаємо бота
CMD ["python", "main2.py"]
