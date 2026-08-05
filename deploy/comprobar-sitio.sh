#!/usr/bin/env bash
#
# comprobar-sitio.sh — comprueba el Observatorio DESDE FUERA, con solo curl.
#
# Uso:  ./deploy/comprobar-sitio.sh <dominio-spa> <dominio-api> [llave-de-busqueda]
#       ./deploy/comprobar-sitio.sh observatorio.predes.org.pe obs.predes.org.pe
#
# Cron en OTRA máquina:
#       */10 * * * * /ruta/comprobar-sitio.sh observatorio.predes.org.pe obs.predes.org.pe \
#                    || mail -s "Observatorio caído" alguien@predes.org.pe
#
# POR QUÉ EXISTE. `deploy/vigilar-contenedores.sh` corre en el servidor y puede *arreglar*:
# reinicia lo que el healthcheck marca enfermo. Pero tiene un punto ciego insalvable — **si el
# servidor entero cae, el vigilante cae con él y nadie se entera**—. Tampoco ve lo que solo se nota
# desde fuera: que el DNS deje de resolver, que el certificado caduque, que el firewall del
# proveedor cierre el 443, o que nginx conteste pero sirva el bundle equivocado.
#
# Por eso este no necesita nada del servidor: ni Docker, ni SSH, ni credenciales, ni el
# repositorio. Solo `curl` y salida a internet. Se copia a cualquier equipo y se cuelga de un cron.
#
# Comprueba, NO arregla. Actuar desde fuera exigiría una clave SSH con permisos sobre Docker
# guardada en otra máquina, y eso es más superficie de la que resuelve.
#
# La llave de búsqueda es opcional: sin ella se omite esa comprobación. Es la
# `VITE_MEILI_SEARCH_KEY` del `.env` de la raíz, y es de solo búsqueda —puede viajar—.

set -Eeuo pipefail
IFS=$'\n\t'

TIEMPO_MAXIMO=15          # segundos por petición: una comprobación que se cuelga no comprueba
DIAS_AVISO_CERT=21        # certbot renueva a los 30 días; por debajo de esto, algo va mal

SPA="${1:-}"
API="${2:-}"
LLAVE="${3:-${VITE_MEILI_SEARCH_KEY:-}}"

if [[ -z "$SPA" || -z "$API" || "$SPA" == "-h" || "$SPA" == "--help" ]]; then
    cat <<EOF
comprobar-sitio.sh — comprueba el Observatorio desde fuera, con solo curl

Uso: ./deploy/comprobar-sitio.sh <dominio-spa> <dominio-api> [llave-de-busqueda]

  <dominio-spa>   el que sirve el sitio            (SITE_DOMAIN)
  <dominio-api>   el del API, admin, media y tiles (API_DOMAIN)
  [llave]         VITE_MEILI_SEARCH_KEY; si falta, se omite esa comprobación
                  (también se toma de la variable de entorno del mismo nombre)

Sale con código != 0 si algo falla, para colgarlo de un «|| mail» en otra máquina.
EOF
    exit 2
fi

if [[ -t 1 ]]; then
    C_RESET=$'\033[0m'; C_VERDE=$'\033[1;32m'; C_ROJO=$'\033[1;31m'; C_GRIS=$'\033[0;90m'
else
    C_RESET=""; C_VERDE=""; C_ROJO=""; C_GRIS=""
fi

FALLOS=0

ok()    { printf '  %s✓%s %-14s %s\n' "$C_VERDE" "$C_RESET" "$1" "$2"; }
mal()   { printf '  %s✗%s %-14s %s\n' "$C_ROJO" "$C_RESET" "$1" "$2"; FALLOS=$((FALLOS + 1)); }
omite() { printf '  %s·%s %-14s %s\n' "$C_GRIS" "$C_RESET" "$1" "$C_GRIS$2$C_RESET"; }

pedir() { curl -s --max-time "$TIEMPO_MAXIMO" "$@"; }

printf '\nObservatorio Kallpachakuy — comprobación externa  (%s)\n\n' "$(date '+%Y-%m-%d %H:%M')"

# --- La SPA ---------------------------------------------------------------
codigo="$(pedir -o /dev/null -w '%{http_code}' "https://$SPA/" || echo 000)"
if [[ "$codigo" == "200" ]]; then ok "SPA" "200"
else mal "SPA" "$codigo  ← https://$SPA/ no responde como debe"; fi

# --- Redirección a HTTPS --------------------------------------------------
codigo="$(pedir -o /dev/null -w '%{http_code}' "http://$SPA/" || echo 000)"
if [[ "$codigo" == "301" || "$codigo" == "308" ]]; then ok "http a https" "$codigo"
else mal "http a https" "$codigo  ← el :80 debería redirigir"; fi

# --- Salud del backend ----------------------------------------------------
# 200 aunque la base o el buscador estén caídos: la sonda mide que el proceso atienda, y el
# detalle viene en el cuerpo. Por eso aquí se mira el cuerpo además del código.
cuerpo="$(pedir "https://$API/api/salud/" || echo '')"
codigo="$(pedir -o /dev/null -w '%{http_code}' "https://$API/api/salud/" || echo 000)"
if [[ "$codigo" == "200" ]]; then
    resumen="$(printf '%s' "$cuerpo" | tr -d '{}"' | tr ',' ' ')"
    if printf '%s' "$cuerpo" | grep -q 'sin respuesta'; then
        mal "API salud" "200 pero degradado: $resumen"
    else
        ok "API salud" "200 $resumen"
    fi
else
    mal "API salud" "$codigo  ← el backend no atiende"
fi

# --- El admin -------------------------------------------------------------
# Se prueba la página de login, no la raíz del admin: la raíz redirige y no distingue
# «el admin está» de «el admin redirige a un 404».
codigo="$(pedir -o /dev/null -w '%{http_code}' "https://$API/loginseguro/login/" || echo 000)"
if [[ "$codigo" == "200" ]]; then ok "admin" "200"
else mal "admin" "$codigo  ← ¿coincide ADMIN_URL con el location de nginx?"; fi

# --- El buscador ----------------------------------------------------------
# 405 significaría que el proxy manda todo a la raíz de Meilisearch. GET /search/health no vale
# como comprobación: la raíz de Meilisearch también responde 200.
if [[ -n "$LLAVE" ]]; then
    codigo="$(pedir -o /dev/null -w '%{http_code}' -X POST \
        -H "Authorization: Bearer $LLAVE" -H 'Content-Type: application/json' \
        -d '{"queries":[{"indexUid":"medidas","q":"cusco","limit":1}]}' \
        "https://$API/search/multi-search" || echo 000)"
    case "$codigo" in
        200) ok  "buscador" "200 (con llave)" ;;
        401|403) mal "buscador" "$codigo  ← la llave del bundle ya no vale en Meilisearch" ;;
        405) mal "buscador" "405  ← el proxy /search/ manda a la raíz de Meilisearch" ;;
        *)   mal "buscador" "$codigo" ;;
    esac
else
    codigo="$(pedir -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' \
        -d '{"queries":[]}' "https://$API/search/multi-search" || echo 000)"
    if [[ "$codigo" == "401" ]]; then ok "buscador" "401 sin llave (el proxy va bien)"
    elif [[ "$codigo" == "405" ]]; then mal "buscador" "405  ← el proxy manda a la raíz"
    else mal "buscador" "$codigo"; fi
fi

# --- El certificado -------------------------------------------------------
# Lo que el vigilante del servidor no puede ver venir: certbot renueva a los 30 días, así que por
# debajo de tres semanas es que la renovación automática no está funcionando.
if command -v openssl >/dev/null 2>&1; then
    fin="$(echo | openssl s_client -connect "$SPA:443" -servername "$SPA" 2>/dev/null \
           | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2 || true)"
    if [[ -n "$fin" ]]; then
        dias=$(( ( $(date -d "$fin" +%s) - $(date +%s) ) / 86400 ))
        if   (( dias < 0 ));                then mal "certificado" "CADUCADO hace $(( -dias )) días"
        elif (( dias < DIAS_AVISO_CERT ));  then mal "certificado" "$dias días  ← la renovación no está funcionando"
        else ok "certificado" "$dias días"; fi
    else
        mal "certificado" "no se pudo leer"
    fi
else
    omite "certificado" "(sin openssl en esta máquina)"
fi

echo
if (( FALLOS == 0 )); then
    printf '  %stodo bien%s\n\n' "$C_VERDE" "$C_RESET"
    exit 0
fi
printf '  %s%d comprobación(es) fallida(s)%s\n\n' "$C_ROJO" "$FALLOS" "$C_RESET"
exit 1
