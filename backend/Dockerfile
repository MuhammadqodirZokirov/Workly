FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml ./
COPY rabotago ./rabotago
RUN pip install .

COPY alembic.ini ./
COPY alembic ./alembic

RUN useradd --create-home app
USER app

EXPOSE 8000
# Faza 1-lite: bitta jarayon (API + bot + scheduler). Polling rejimida worker faqat 1 ta bo'lishi shart.
CMD ["sh", "-c", "alembic upgrade head && python -m rabotago.infrastructure.seed && uvicorn rabotago.interfaces.api.asgi:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
