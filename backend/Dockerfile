# Etapa 1: compilar tippecanoe (genera PMTiles nativamente desde v2.17).
FROM debian:bookworm-slim AS tippecanoe
RUN apt-get update && apt-get install -y --no-install-recommends \
        git build-essential libsqlite3-dev zlib1g-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 https://github.com/felt/tippecanoe.git /tmp/tippecanoe \
    && make -C /tmp/tippecanoe -j"$(nproc)" \
    && make -C /tmp/tippecanoe install

# Etapa 2: runtime Django.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Dependencias de sistema: weasyprint (pango/cairo), tippecanoe (sqlite/zlib).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
        libffi8 shared-mime-info fonts-dejavu-core \
        libsqlite3-0 zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY --from=tippecanoe /usr/local/bin/tippecanoe /usr/local/bin/tippecanoe
COPY --from=tippecanoe /usr/local/bin/tippecanoe-decode /usr/local/bin/tippecanoe-decode
COPY --from=tippecanoe /usr/local/bin/tile-join /usr/local/bin/tile-join
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY . .
ENV PATH="/app/.venv/bin:$PATH"

RUN SECRET_KEY=collectstatic python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
