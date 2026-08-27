#!/usr/bin/env bash
#
# desplegar.sh — despliega en ESTE servidor la versión que hay en origin/<rama>.
#
# Uso:  ./deploy/desplegar.sh              # despliega origin/master
#       RAMA_DESPLIEGUE=otra ./deploy/desplegar.sh
#
# Lo lanza Bitbucket Pipelines por SSH en cada push a master (ver bitbucket-pipelines.yml), pero
# **vale exactamente igual lanzado a mano**: el CI no es un procedimiento paralelo, solo es quien
# llama. Si este script no sirve desde una terminal, no sirve.
#
# POR QUÉ EXISTE. El 27/08/2026 el sitio estuvo sirviendo el bundle del 11/08 sin que nada fallara.
# El despliegue se había hecho con `docker compose up -d` **sin `--build`**: como el servicio
# `frontend` es de un solo disparo y su CMD vuelve a copiar su dist al volumen que sirve nginx, el
# sitio se «refrescó» —index.html con fecha de ese día— con el bundle de dieciséis días antes.
# Códigos 200, contenedores healthy, cero errores en los logs. **Un despliegue a medias se ve
# idéntico a uno correcto**, y la cadena de cinco comandos del runbook se recordaba mal.
#
# De ahí las dos cosas que hace este script y que no hacía la cadena manual:
#
#   1. SELLA la versión desplegada en /version.txt, dentro del propio dist que sirve nginx.
#   2. La VERIFICA desde fuera, por HTTPS, contra el commit que acaba de desplegar.
#
# Así «está desplegado» deja de ser una suposición y pasa a ser algo que se comprueba con curl.

set -Eeuo pipefail
IFS=$'\n\t'

# Por SSH con `command=` el entorno es mínimo y puede no traer docker en el PATH.
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

RAIZ="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

RAMA="${RAMA_DESPLIEGUE:-master}"
ESPERA_SALUD=210          # segundos: el backend tiene start_period de 90 s (migrate + meili_setup)

# Todo despliegue queda registrado, venga de donde venga. Mismo sitio que vigilancia.log.
REGISTRO="${HOME:-/tmp}/observatorio-registros/despliegue.log"
mkdir -p -- "$(dirname -- "$REGISTRO")"
exec > >(tee -a -- "$REGISTRO") 2>&1

if [[ -t 1 ]]; then
    C_RESET=$'\033[0m'; C_VERDE=$'\033[1;32m'; C_ROJO=$'\033[1;31m'; C_AZUL=$'\033[1;34m'
else
    C_RESET=""; C_VERDE=""; C_ROJO=""; C_AZUL=""
fi

paso()  { printf '\n%s==>%s %s\n' "$C_AZUL" "$C_RESET" "$1"; }
ok()    { printf '  %s✓%s %s\n' "$C_VERDE" "$C_RESET" "$1"; }
abortar() { printf '\n  %s✗ %s%s\n\n' "$C_ROJO" "$1" "$C_RESET" >&2; exit 1; }

printf '\n%s— despliegue del Observatorio —%s  %s\n' "$C_AZUL" "$C_RESET" "$(date '+%Y-%m-%d %H:%M:%S')"

# --- 1. El árbol tiene que estar limpio -----------------------------------
# Un despliegue no es el momento de descubrir trabajo a medias. Solo mira archivos trackeados:
# lo no versionado (data.old/, registros) no bloquea nada.
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    git status --short --untracked-files=no
    abortar "hay cambios locales sin commitear; el despliegue no los va a pisar"
fi

actual="$(git rev-parse --abbrev-ref HEAD)"
[[ "$actual" == "$RAMA" ]] || abortar "el árbol está en «$actual» y se pidió desplegar «$RAMA»"

# --- 2. Traer la versión a desplegar --------------------------------------
paso "Trayendo origin/$RAMA"
git fetch --quiet origin "$RAMA"
# --ff-only a propósito: si la historia divergió, que falle en vez de fabricar un merge en el
# servidor. Un merge hecho aquí no está en Bitbucket y nadie lo vería nunca.
git pull --ff-only origin "$RAMA"

SHA="$(git rev-parse HEAD)"
ok "$(git log -1 --format='%h %s' HEAD)"

# --- 3. Construir ---------------------------------------------------------
# Los tres servicios que llevan código propio. `worker` comparte contexto con `backend` pero es
# imagen aparte: sin él, la cola seguiría corriendo el código viejo.
paso "Construyendo imágenes"
docker compose build backend worker frontend

paso "Levantando servicios"
docker compose up -d

# --- 4. Publicar el dist y sellarlo ---------------------------------------
# Este es el paso que se olvidó: es lo único que copia el dist nuevo al volumen que sirve nginx.
paso "Publicando el frontend"
docker compose run --rm frontend

# El sello va DESPUÉS: el CMD del servicio empieza con `rm -rf /out/*` y se lo llevaría por delante.
docker compose run --rm frontend sh -c "printf '%s\n' '$SHA' > /out/version.txt"
ok "dist publicado y sellado con $SHA"

# --- 5. Recargar nginx ----------------------------------------------------
# Obligatorio si el pull tocó deploy/nginx/conf.d/: el archivo montado cambia, pero el proceso
# sigue con el que cargó al arrancar y `up -d` no recrea nginx porque su definición no cambió.
# El síntoma sería un 404, no un error. Es barato, así que se hace siempre.
paso "Recargando nginx"
# `nginx -t` antes, y no solo por prudencia: `nginx -s reload` **devuelve 0 aunque la
# configuración esté rota** —solo manda la señal, y el maestro rechaza la recarga por su cuenta
# escribiendo el error en su log—. Sin esta comprobación, un error de sintaxis en conf.d pasaría
# el despliegue en verde dejando nginx con la configuración anterior.
docker compose exec -T nginx nginx -t
docker compose exec -T nginx nginx -s reload
ok "recargado"

# --- 6. Esperar a que el backend esté sano --------------------------------
paso "Esperando al backend"
cid="$(docker compose ps -q backend)"
[[ -n "$cid" ]] || abortar "el contenedor backend no está levantado"
esperado=0
while (( esperado < ESPERA_SALUD )); do
    estado="$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo desconocido)"
    [[ "$estado" == "healthy" ]] && break
    sleep 5
    esperado=$(( esperado + 5 ))
done
[[ "${estado:-}" == "healthy" ]] || abortar "el backend sigue «${estado:-?}» tras $ESPERA_SALUD s — mira \`docker compose logs backend\`"
ok "healthy en ${esperado}s"

# --- 7. Verificar desde fuera ---------------------------------------------
# La comprobación que no existía. Los dominios y la llave salen del .env de la raíz.
set -a; . ./.env; set +a

paso "Verificando el despliegue desde fuera"
servido="$(curl -fsS --max-time 15 "https://${SITE_DOMAIN}/version.txt" 2>/dev/null | tr -d '[:space:]' || echo '')"
if [[ "$servido" != "$SHA" ]]; then
    abortar "https://${SITE_DOMAIN} sirve «${servido:-nada}» y se desplegó «$SHA» — el bundle publicado NO es el de este commit"
fi
ok "https://${SITE_DOMAIN} sirve $SHA"

"$RAIZ/deploy/comprobar-sitio.sh" "$SITE_DOMAIN" "$API_DOMAIN" "${VITE_MEILI_SEARCH_KEY:-}" "$SHA"

printf '\n  %sdesplegado%s  %s\n\n' "$C_VERDE" "$C_RESET" "$SHA"
