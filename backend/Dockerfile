# Imagem de produção da API Músicas Babuínas.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home --uid 10001 babuino
USER babuino

EXPOSE 8000

# As migrações rodam na inicialização (ver app/main.py). Logs de acesso desativados:
# não registramos IPs de jogadores. --proxy-headers usa o IP real atrás do proxy do host
# apenas para o limitador de requisições (em memória).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
