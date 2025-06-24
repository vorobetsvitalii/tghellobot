FROM python:3.11-slim

WORKDIR /app

# Встановлюємо сертифікати для HTTPS
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Під час pip install вказуємо trusted-host
RUN pip install --no-cache-dir \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    python-telegram-bot==20.6

COPY . .

CMD ["python", "main2.py"]
