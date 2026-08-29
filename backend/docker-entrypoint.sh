#!/usr/bin/env bash
# Arranque del backend y del worker.
#
# `migrate`, `meili_setup` y `collectstatic` son idempotentes, así que correrlos en cada arranque
# es seguro y evita el paso manual que se olvida justo el día del despliegue.
set -euo pipefail

# El worker no debe migrar: si backend y worker arrancan a la vez, dos `migrate` en paralelo
# compiten por el lock de la tabla de migraciones.
if [ "${1:-}" = "python" ] && [ "${3:-}" = "db_worker" ]; then
    echo "==> worker: esperando a que la base esté migrada"
    until python manage.py migrate --check >/dev/null 2>&1; do sleep 2; done
else
    echo "==> migrando la base de datos"
    python manage.py migrate --noinput

    echo "==> preparando los índices de búsqueda"
    python manage.py meili_setup --tolerante || true

    # `collectstatic` YA corre en el Dockerfile, pero su resultado no llega a producción: en
    # `compose.yaml` el volumen `static` se monta encima de /app/staticfiles, y **Docker solo
    # siembra un volumen nombrado cuando está vacío**. A partir del segundo despliegue, lo que
    # escribió el build queda tapado por el contenido viejo del volumen.
    #
    # Y el fallo no es cosmético: con `CompressedManifestStaticFilesStorage`, un archivo que no
    # esté en `staticfiles.json` hace que Django lance `ValueError: Missing staticfiles manifest
    # entry` — o sea **HTTP 500** en esa pantalla del admin, no un CSS ausente.
    #
    # Sin `--clear` a propósito: vaciar el directorio deja una ventana en la que nginx —que sirve
    # /static/ directamente desde el volumen— responde 404. Los huérfanos que quedan son inocuos
    # y de hecho cubren al navegador que aún tenga el HTML anterior en caché.
    echo "==> publicando los archivos estáticos"
    python manage.py collectstatic --noinput
fi

exec "$@"
