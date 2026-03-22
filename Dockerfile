FROM python:3.12-slim AS builder

RUN groupadd -r appgroup && useradd -r -m -g appgroup appuser

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get install -y --no-install-recommends gcc netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

RUN set -x && pip install --upgrade pip && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

COPY entrypoints /app/entrypoints

COPY src /app/src


RUN chgrp appgroup /app/entrypoints/*.sh && \
    chmod +x /app/entrypoints/*.sh



FROM builder AS final

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc netcat-openbsd && \
    pip install awscli awscli-local && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app

USER appuser
