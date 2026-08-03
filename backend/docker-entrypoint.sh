#!/usr/bin/env bash
# Arranque del backend y del worker.
#
# `migrate` y `meili_setup` son idempotentes, así que correrlos en cada arranque es seguro y
# evita el paso manual que se olvida justo el día del despliegue.
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
fi

exec "$@"
