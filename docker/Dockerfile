FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY src ./src
COPY sdk ./sdk
COPY integrations/mcp/src ./integrations/mcp/src
COPY migrations ./migrations

RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 agentpost \
    && mkdir -p /data/attachments \
    && chown -R agentpost:agentpost /data

USER agentpost

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn agentpost.main:app --host 0.0.0.0 --port 8000"]
