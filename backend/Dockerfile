# Imagen del backend: Django + gunicorn, con el pipeline geoespacial y el navegador headless
# que necesitan los tiles (spec 05) y el mapa de la ayuda memoria (spec 02).

# Etapa 1: compilar tippecanoe. Hace falta >= 2.17, que es donde aparece la escritura nativa de
# PMTiles; con versiones anteriores habría que pasar por MBTiles y convertir. No hay paquete
# Debian, así que se compila aquí y solo se copian los binarios a la imagen final.
FROM debian:bookworm-slim AS tippecanoe
RUN apt-get update && apt-get install -y --no-install-recommends \
        git build-essential libsqlite3-dev zlib1g-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 https://github.com/felt/tippecanoe.git /tmp/tippecanoe \
    && make -C /tmp/tippecanoe -j"$(nproc)" \
    && make -C /tmp/tippecanoe install

# Etapa 2: runtime.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    # Playwright dentro de la imagen, no en el HOME del usuario: el contenedor puede correr con
    # un HOME que no existe o no es escribible.
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# Dependencias de sistema, por qué está cada grupo:
#   pango/cairo/gdk-pixbuf → WeasyPrint (ayuda memoria PDF, ADR-A9)
#   gdal-bin               → ogr2ogr/ogrinfo: reproyección y recorte de capas (spec 05)
#   sqlite/zlib            → runtime de tippecanoe
#   fonts-dejavu           → el PDF sin fuentes sale con cajas en vez de texto
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
        libffi8 shared-mime-info fonts-dejavu-core \
        gdal-bin \
        libsqlite3-0 zlib1g \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=tippecanoe /usr/local/bin/tippecanoe /usr/local/bin/tippecanoe
COPY --from=tippecanoe /usr/local/bin/tippecanoe-decode /usr/local/bin/tippecanoe-decode
COPY --from=tippecanoe /usr/local/bin/tile-join /usr/local/bin/tile-join
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
# Por defecto sin dependencias de desarrollo. `compose.dev.yml` construye con
# `GRUPOS_UV=--group dev` para que pytest exista **dentro de la imagen**: correr la suite en el
# contenedor es lo que garantiza que se prueba con las mismas versiones de GDAL, tippecanoe y
# WeasyPrint que producción, y no con las que haya en la máquina de quien programa.
ARG GRUPOS_UV=--no-dev
RUN uv sync ${GRUPOS_UV}

ENV PATH="/app/.venv/bin:$PATH"

# Chromium para capturar el mapa del PDF. `--with-deps` trae las libs del sistema que necesita;
# va después de `uv sync` porque el binario de playwright vive en el venv.
RUN playwright install --with-deps chromium && rm -rf /var/lib/apt/lists/*

COPY . .

RUN SECRET_KEY=collectstatic python manage.py collectstatic --noinput

# Arranque: migrar y preparar los índices antes de servir. `meili_setup --tolerante` no aborta
# si Meilisearch aún no responde — la búsqueda es una función del sitio, no un requisito para
# servirlo, y el arranque no debe depender del orden en que suban los contenedores.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "3", "--timeout", "120", "--access-logfile", "-"]
