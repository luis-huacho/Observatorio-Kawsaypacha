#!/usr/bin/env bash
#
# vigilar-contenedores.sh — reinicia los contenedores que el healthcheck marca «unhealthy».
#
# Uso:  ./deploy/vigilar-contenedores.sh [--dry-run]
# Cron: */2 * * * * cd <repo> && ./deploy/vigilar-contenedores.sh
#
# POR QUÉ EXISTE. `restart: unless-stopped` solo actúa si el **proceso muere**. El fallo que no
# cubre es el contrario: gunicorn con los tres workers bloqueados, vivo y sin atender. El
# contenedor figura `Up`, el sitio devuelve timeouts y nadie hace nada. Y **Docker Compose no
# reinicia un contenedor «unhealthy»**: los healthchecks solo pintan estado, no actúan. Hace falta
# alguien que mire y decida, y es esto.
#
# POR QUÉ EN EL ANFITRIÓN Y NO UN CONTENEDOR `autoheal`. La imagen estándar exige montar
# /var/run/docker.sock, que es la API de Docker sin autenticación: quien la alcanza puede arrancar
# un contenedor privilegiado y montar el disco del anfitrión. Eso es root del servidor, cedido a un
# contenedor, en una máquina pública. Desde fuera se hace lo mismo sin ceder nada. Además, el único
# precedente de vigilancia del proyecto ya es cron del anfitrión (`meili_estado || mail`), y añadir
# una pieza que PREDES no sabría depurar es justo lo que evitó ADR-A6bis al descartar Caddy.
#
# POR QUÉ AQUÍ SÍ SE ARREGLA SOLO, si `meili_estado` dice «comprueba, no arregla». No es el mismo
# caso: reindexar por tu cuenta a las cuatro de la mañana destruye información y sustituye una
# decisión humana. Reiniciar un servidor web colgado no destruye nada, es el remedio estándar, y la
# alternativa es un sitio caído hasta que alguien lo mire. Por eso el **worker se queda fuera**: si
# se atasca a mitad de una importación de 10,978 filas, reiniciarlo puede dejar el dato peor que
# parado, así que ahí solo se avisa (`manage.py cola_estado`).
#
# EL TOPE ES LA PARTE IMPORTANTE. Un reinicio que no arregla el problema no puede convertirse en un
# bucle: borraría el rastro justo cuando hay que diagnosticar, y un contenedor reiniciándose cada
# dos minutos es más difícil de depurar que uno parado. Al llegar al tope deja de actuar y lo
# registra, que es lo que hay que ver en el log.

set -Eeuo pipefail
IFS=$'\n\t'

REGISTROS="${OBSERVATORIO_REGISTROS:-$HOME/observatorio-registros}"
BITACORA="$REGISTROS/vigilancia.log"
CONTADOR="$REGISTROS/vigilancia.estado"

MAX_REINICIOS=3          # por servicio
VENTANA=3600             # segundos: los reinicios más viejos que esto ya no cuentan

DRY_RUN="no"

usage() {
    cat <<EOF
vigilar-contenedores.sh — reinicia los contenedores «unhealthy» de este proyecto

Uso: ./deploy/vigilar-contenedores.sh [--dry-run]

  --dry-run    Decir qué se reiniciaría, sin tocar nada
  -h, --help   Esta ayuda

Reinicia como máximo $MAX_REINICIOS veces por servicio y hora; pasado el tope solo registra.
Registro y contador en \$OBSERVATORIO_REGISTROS (por defecto ~/observatorio-registros).

El worker queda fuera a propósito: ver la cabecera del script.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN="yes"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "opción desconocida: $1" >&2; usage; exit 2 ;;
    esac
done

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

PROYECTO="$(basename "$RAIZ")"

mkdir -p "$REGISTROS"
touch "$CONTADOR"

registrar() {
    printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$BITACORA"
}

# Reinicios del servicio dentro de la ventana. El contador es un archivo de líneas
# «servicio epoch», que se poda en cada pasada: no hace falta nada más que un archivo de texto.
reinicios_recientes() {
    local servicio="$1" limite=$(( $(date +%s) - VENTANA ))
    awk -v s="$servicio" -v l="$limite" '$1 == s && $2 >= l' "$CONTADOR" | wc -l
}

podar_contador() {
    local limite=$(( $(date +%s) - VENTANA )) tmp
    tmp="$(mktemp)"
    awk -v l="$limite" '$2 >= l' "$CONTADOR" > "$tmp" 2>/dev/null || true
    mv "$tmp" "$CONTADOR"
}

podar_contador

# `--filter health=unhealthy` acotado al proyecto: en un servidor con más de un compose, esto no
# puede ir reiniciando contenedores ajenos.
#
# Ojo con la plantilla: en `docker ps`, `.Labels` es una CADENA con todas las etiquetas separadas
# por comas, no un mapa —el mapa es `.Config.Labels`, y eso es de `docker inspect`—. La forma
# correcta aquí es la función `.Label`. Con `index .Labels` docker falla con «cannot index
# slice/array with type string», y sin la comprobación de abajo ese fallo se leería como «no hay
# nada enfermo»: el vigilante callado y roto, que es la peor de las averías.
if ! enfermos="$(docker ps \
    --filter "label=com.docker.compose.project=$PROYECTO" \
    --filter health=unhealthy \
    --format '{{.Label "com.docker.compose.service"}}' 2>&1 | sort -u)"; then
    registrar "no se pudo consultar el estado de los contenedores: $enfermos"
    exit 1
fi
# `docker ps` puede terminar con éxito y escribir el error de plantilla por stdout.
if [[ "$enfermos" == *"failed to execute template"* || "$enfermos" == *"error calling"* ]]; then
    registrar "la plantilla de docker ps falló: $enfermos"
    exit 1
fi

if [[ -z "$enfermos" ]]; then
    exit 0        # el caso normal: ni una línea en el log, para que el log signifique algo
fi

for servicio in $enfermos; do
    # El worker no tiene healthcheck, así que no debería aparecer nunca; la guarda está por si
    # alguien se lo añade sin leer la cabecera de este archivo.
    if [[ "$servicio" == "worker" ]]; then
        registrar "worker «unhealthy»: NO se reinicia por diseño; revisar con «manage.py cola_estado»"
        continue
    fi

    previos="$(reinicios_recientes "$servicio")"
    if (( previos >= MAX_REINICIOS )); then
        registrar "$servicio «unhealthy»: TOPE alcanzado ($previos en la última hora). No se reinicia; hay que mirarlo a mano: docker compose logs $servicio"
        continue
    fi

    if [[ "$DRY_RUN" == "yes" ]]; then
        registrar "[dry-run] $servicio «unhealthy»: se reiniciaría (van $previos en la última hora)"
        echo "[dry-run] reiniciaría $servicio (van $previos en la última hora)"
        continue
    fi

    if docker compose restart "$servicio" >/dev/null 2>&1; then
        printf '%s %s\n' "$servicio" "$(date +%s)" >> "$CONTADOR"
        registrar "$servicio «unhealthy»: reiniciado (van $(( previos + 1 )) en la última hora)"
    else
        registrar "$servicio «unhealthy»: el reinicio FALLÓ; docker compose logs $servicio"
    fi
done
