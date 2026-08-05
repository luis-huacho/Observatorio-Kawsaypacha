#!/usr/bin/env bash
#
# inicializar.sh — deja el Gitea de `compose.tracking.yaml` listo para usarse como tracker.
#
# Uso:  docker compose -f compose.tracking.yaml up -d
#       ./deploy/gitea/inicializar.sh
#
# Crea, si no existen: el usuario administrador, un token de acceso, el repositorio de issues y las
# etiquetas de severidad y área. **Es idempotente**: correrlo dos veces seguidas no cambia nada y
# sale 0. Esa es la razón de que exista — el asistente web del primer arranque hace lo mismo, pero
# a mano y sin dejar rastro en el repositorio, así que nadie puede reproducir la instalación.
#
# Las credenciales del administrador **las genera él** (`admin<NNN>` / `PREDES.<NNN>.<año>`) y no
# están escritas en ningún archivo versionado. Si encuentra un administrador con un nombre que no
# encaja en ese patrón, lo renombra: los issues conservan su autoría y el token del MCP sigue
# valiendo, porque van atados al usuario y no a su nombre.
#
# Escribe dos archivos, los dos ignorados por git:
#
#   deploy/gitea/admin.env   usuario y contraseña del admin (para entrar por la web)
#   deploy/gitea/token.env   GITEA_HOST y GITEA_ACCESS_TOKEN, y nada más
#
# Van separados a propósito: `token.env` se le pasa entero al contenedor del servidor MCP con
# `--env-file` (ver `.mcp.json`), y la contraseña del admin no tiene por qué viajar ahí dentro.
#
# `GITEA_HOST` es http://localhost:3000 —no el nombre de servicio de la red de compose— y eso
# obliga al contenedor del MCP a correr con `--network host`. La razón es que **Gitea construye los
# `html_url` de su API a partir de la cabecera `Host` de la petición**, no de `ROOT_URL`: entrando
# por `http://gitea:3000` devolvería enlaces que no se pueden abrir en el navegador.

set -Eeuo pipefail
IFS=$'\n\t'

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIR="$RAIZ/deploy/gitea"
COMPOSE=(docker compose -f "$RAIZ/compose.tracking.yaml")

URL_LOCAL="http://localhost:3000"       # puerto publicado en loopback; ver la nota de la cabecera
CORREO="${GITEA_ADMIN_EMAIL:-observatorio@predes.org.pe}"
REPO="${GITEA_REPO:-observatorio}"
PATRON_USUARIO='^admin[0-9]{3}$'
NOMBRE_TOKEN="claude-mcp"
ALCANCES="write:repository,write:issue,read:user"

if [[ -t 1 ]]; then
    C_RESET=$'\033[0m'; C_VERDE=$'\033[1;32m'; C_ROJO=$'\033[1;31m'; C_GRIS=$'\033[0;90m'
else
    C_RESET=""; C_VERDE=""; C_ROJO=""; C_GRIS=""
fi

hecho()  { printf '%s✓%s %s\n' "$C_VERDE" "$C_RESET" "$1"; }
igual()  { printf '%s·%s %s%s%s\n' "$C_GRIS" "$C_RESET" "$C_GRIS" "$1" "$C_RESET"; }
morir()  { printf '%s✗%s %s\n' "$C_ROJO" "$C_RESET" "$1" >&2; exit 1; }

# ---------------------------------------------------------------- 1. el contenedor está en pie

printf 'Esperando a que Gitea responda en %s ' "$URL_LOCAL"
for _ in $(seq 1 40); do
    if curl -fsS --max-time 3 "$URL_LOCAL/api/healthz" >/dev/null 2>&1; then
        printf '\n'; hecho "Gitea responde"
        break
    fi
    printf '.'; sleep 2
done
curl -fsS --max-time 3 "$URL_LOCAL/api/healthz" >/dev/null 2>&1 \
    || morir "Gitea no responde. ¿Levantaste 'docker compose -f compose.tracking.yaml up -d'?"

# ---------------------------------------------------------------- 2. usuario administrador

gitea_cli() { "${COMPOSE[@]}" exec -T -u git gitea gitea "$@"; }

# Las credenciales se GENERAN, no vienen escritas en ninguna parte: así no acaban en el historial de
# git, y cada instalación tiene las suyas. El patrón es el acordado con el dueño del proyecto.
#
# Los dos números son independientes a propósito. Con el mismo, conocer el usuario regalaría la
# mitad de la contraseña, y esto puede acabar tras un login expuesto a internet.
#
# OJO CON LA FUERZA DEL SECRETO: el patrón es público y solo varían tres dígitos, o sea **900
# combinaciones**. Eso NO aguanta un ataque por fuerza bruta sostenido; lo único que hay delante es
# el `limit_req` de nginx. Si el tracker se publica en `/gitea`, cambiar la contraseña por una de
# verdad desde la web —o restringir por IP— deja de ser opcional. Está dicho en el README.
tres_digitos() { printf '%d' $(( $(od -An -N2 -tu2 < /dev/urandom) % 900 + 100 )); }
nuevo_usuario() { printf 'admin%s' "$(tres_digitos)"; }
nueva_clave()   { printf 'PREDES.%s.%s' "$(tres_digitos)" "$(date +%Y)"; }

escribir_admin_env() {
    umask 077
    cat > "$DIR/admin.env" <<EOF
# Credenciales del admin de Gitea, generadas por deploy/gitea/inicializar.sh.
# Sirven para entrar por la web. No se versionan: git ignora deploy/gitea/*.env.
GITEA_ADMIN_USER=$USUARIO
GITEA_ADMIN_PASSWORD=$CLAVE
EOF
}

# El archivo manda; el entorno puede forzarlo para reproducir una instalación concreta.
USUARIO="${GITEA_ADMIN_USER:-$(sed -n 's/^GITEA_ADMIN_USER=//p' "$DIR/admin.env" 2>/dev/null)}"
CLAVE="${GITEA_ADMIN_PASSWORD:-$(sed -n 's/^GITEA_ADMIN_PASSWORD=//p' "$DIR/admin.env" 2>/dev/null)}"
EN_GITEA="$(gitea_cli admin user list 2>/dev/null | awk 'NR>1 {print $2}')"

if [[ -z "$USUARIO" ]]; then
    # Instalación nueva. Si ya hubiera usuarios, no sabríamos su contraseña y no podríamos seguir.
    [[ -z "$EN_GITEA" ]] || morir \
        "Gitea ya tiene usuarios ($(tr '\n' ' ' <<< "$EN_GITEA")) y falta deploy/gitea/admin.env con
   la contraseña de alguno. Opciones: exportar GITEA_ADMIN_USER y GITEA_ADMIN_PASSWORD, o empezar
   de cero con 'docker compose -f compose.tracking.yaml down -v' (se pierden los issues)."
    USUARIO="$(nuevo_usuario)"; CLAVE="$(nueva_clave)"
    gitea_cli admin user create --username "$USUARIO" --email "$CORREO" --password "$CLAVE" \
        --admin --must-change-password=false >/dev/null
    escribir_admin_env
    hecho "Usuario '$USUARIO' creado — credenciales en deploy/gitea/admin.env"

elif ! grep -qx "$USUARIO" <<< "$EN_GITEA"; then
    # Está en admin.env pero no en Gitea: el volumen se recreó por debajo.
    [[ -n "$CLAVE" ]] || morir "deploy/gitea/admin.env no trae GITEA_ADMIN_PASSWORD"
    gitea_cli admin user create --username "$USUARIO" --email "$CORREO" --password "$CLAVE" \
        --admin --must-change-password=false >/dev/null
    hecho "Usuario '$USUARIO' recreado con las credenciales guardadas"

elif [[ ! "$USUARIO" =~ $PATRON_USUARIO ]]; then
    # El administrador tiene un nombre que no encaja con el patrón —una cuenta personal de antes de
    # que esto se generase—. Se renombra en vez de crear otro: `rename` conserva la autoría de los
    # issues y el token del MCP, que van atados al usuario y no a su nombre.
    [[ -n "$CLAVE" ]] || morir "deploy/gitea/admin.env no trae GITEA_ADMIN_PASSWORD"
    VIEJO="$USUARIO"
    USUARIO="$(nuevo_usuario)"
    curl -fsS -X POST -u "$VIEJO:$CLAVE" -H "Content-Type: application/json" \
        -d "$(jq -nc --arg n "$USUARIO" '{new_username: $n}')" \
        "$URL_LOCAL/api/v1/admin/users/$VIEJO/rename" >/dev/null
    CLAVE="$(nueva_clave)"
    gitea_cli admin user change-password --username "$USUARIO" --password "$CLAVE" \
        --must-change-password=false >/dev/null
    escribir_admin_env
    hecho "Administrador '$VIEJO' renombrado a '$USUARIO', con contraseña nueva"
    igual "Los issues conservan su autoría y el token del MCP sigue valiendo"

else
    igual "El administrador '$USUARIO' ya está como debe"
    [[ -n "$CLAVE" ]] || morir "deploy/gitea/admin.env no trae GITEA_ADMIN_PASSWORD"
fi

# ---------------------------------------------------------------- 3. token de acceso
#
# El arranque habla con el API por autenticación básica, no con el token que va a crear. Dos razones:
# los endpoints /users/{u}/tokens solo aceptan básica —Gitea no deja que un token gestione tokens—,
# y `POST /user/repos` exige el alcance `write:user`, que es más ancho de lo que el MCP necesita.
# Haciendo el arranque con la contraseña, el token que queda guardado tiene lo justo para su trabajo.

api() {
    local metodo="$1" ruta="$2"; shift 2
    curl -fsS -X "$metodo" -u "$USUARIO:$CLAVE" \
        -H "Content-Type: application/json" \
        "$URL_LOCAL/api/v1$ruta" "$@"
}

con_token() {
    local metodo="$1" ruta="$2"; shift 2
    curl -fsS -X "$metodo" -H "Authorization: token $TOKEN" \
        -H "Content-Type: application/json" \
        "$URL_LOCAL/api/v1$ruta" "$@"
}

TOKEN=""
if [[ -f "$DIR/token.env" ]]; then
    TOKEN="$(sed -n 's/^GITEA_ACCESS_TOKEN=//p' "$DIR/token.env")"
    # Un token guardado no sirve de nada si el volumen se recreó por debajo: se comprueba de verdad.
    if [[ -n "$TOKEN" ]] && con_token GET /user >/dev/null 2>&1; then
        igual "El token de deploy/gitea/token.env sigue siendo válido"
    else
        igual "El token guardado ya no vale; se genera otro"
        TOKEN=""
    fi
fi

if [[ -z "$TOKEN" ]]; then
    # El nombre del token es único por usuario y Gitea no devuelve el valor de uno ya creado. Si
    # quedó uno huérfano de una corrida anterior, se borra antes de pedir el nuevo.
    VIEJO="$(api GET "/users/$USUARIO/tokens?limit=100" \
        | jq -r --arg n "$NOMBRE_TOKEN" '.[] | select(.name == $n) | .id')"
    if [[ -n "$VIEJO" ]]; then
        api DELETE "/users/$USUARIO/tokens/$VIEJO" >/dev/null
        igual "Token '$NOMBRE_TOKEN' huérfano borrado"
    fi
    TOKEN="$(api POST "/users/$USUARIO/tokens" -d "$(jq -nc \
        --arg n "$NOMBRE_TOKEN" --arg s "$ALCANCES" \
        '{name: $n, scopes: ($s | split(","))}')" | jq -r '.sha1')"
    [[ -n "$TOKEN" && "$TOKEN" != "null" ]] || morir "No se pudo generar el token de acceso"
    hecho "Token '$NOMBRE_TOKEN' generado ($ALCANCES)"
fi

# El archivo se reescribe siempre, aunque el token no haya cambiado: así una corrida vieja que dejó
# GITEA_HOST apuntando a otro sitio se corrige sola en la siguiente.
umask 077
cat > "$DIR/token.env" <<EOF
# Generado por deploy/gitea/inicializar.sh. Lo consume el servidor MCP de .mcp.json vía --env-file,
# así que aquí NO va nada más que estas dos variables. No se versiona.
GITEA_HOST=$URL_LOCAL
GITEA_ACCESS_TOKEN=$TOKEN
EOF

# ---------------------------------------------------------------- 4. repositorio

if api GET "/repos/$USUARIO/$REPO" >/dev/null 2>&1; then
    igual "El repositorio '$USUARIO/$REPO' ya existe"
else
    api POST /user/repos -d "$(jq -nc \
        --arg n "$REPO" \
        '{name: $n, description: "Errores y pendientes del Observatorio Kallpachakuy", private: true, auto_init: false}')" \
        >/dev/null
    # Wiki, releases y proyectos solo añaden pestañas vacías a un repositorio que es un tracker.
    api PATCH "/repos/$USUARIO/$REPO" -d \
        '{"has_issues": true, "has_wiki": false, "has_projects": false, "has_releases": false, "has_packages": false, "has_actions": false}' \
        >/dev/null
    hecho "Repositorio '$USUARIO/$REPO' creado"
fi

# ---------------------------------------------------------------- 5. etiquetas
#
# El separador es «/» y no «:» porque Gitea trata las etiquetas con «/» como *scoped labels*: de
# un mismo ámbito solo se puede tener una a la vez. Así un error no puede quedar marcado «alta» y
# «baja» al mismo tiempo, ni pertenecer a dos áreas.

etiqueta() {
    local nombre="$1" color="$2" descripcion="$3"
    if [[ -n "${ETIQUETAS_EXISTENTES:-}" ]] && grep -qxF "$nombre" <<< "$ETIQUETAS_EXISTENTES"; then
        return 0
    fi
    api POST "/repos/$USUARIO/$REPO/labels" -d "$(jq -nc \
        --arg n "$nombre" --arg c "$color" --arg d "$descripcion" \
        '{name: $n, color: $c, description: $d, exclusive: ($n | test("/"))}')" >/dev/null
    printf '  + %s\n' "$nombre"
}

ETIQUETAS_EXISTENTES="$(api GET "/repos/$USUARIO/$REPO/labels?limit=100" | jq -r '.[].name')"
CREADAS_ANTES="$(grep -c . <<< "$ETIQUETAS_EXISTENTES" || true)"

etiqueta "sev/alta"  "#d73a4a" "Lo ve el público o afecta a lo que PREDES entrega. Bloquea la puesta en línea"
etiqueta "sev/media" "#fbca04" "Degrada el sistema sin romperlo, o es un riesgo fuera de nuestro control"
etiqueta "sev/baja"  "#0e8a16" "Cosmético, de mantenimiento o de documentación"

etiqueta "area/backend"    "#1f6feb" "Django, DRF, modelos, comandos de gestión"
etiqueta "area/frontend"   "#8250df" "React, rutas, componentes, api.ts"
etiqueta "area/mapas"      "#0969da" "MapLibre, PMTiles, pipeline de capas, CCPP"
etiqueta "area/buscador"   "#bf8700" "Meilisearch, índices, facetas, sincronización"
etiqueta "area/admin"      "#6e7781" "Unfold, flujo editorial, importadores, Gemini"
etiqueta "area/despliegue" "#116329" "compose, nginx, certificados, backups, vigilancia"
etiqueta "area/datos"      "#953800" "Calidad de la data de origen, cifras, unidades"
etiqueta "area/docs"       "#57606a" "Specs, README, documentación técnica"

etiqueta "sin-prueba" "#cf222e" "No es un defecto de código: cierra por revisión a ojo, no por una prueba que pasa"

CREADAS_AHORA="$(api GET "/repos/$USUARIO/$REPO/labels?limit=100" | jq -r '.[].name' | grep -c . || true)"
if (( CREADAS_AHORA == CREADAS_ANTES )); then
    igual "Las $CREADAS_AHORA etiquetas ya estaban"
else
    hecho "Etiquetas: $CREADAS_ANTES → $CREADAS_AHORA"
fi

# ---------------------------------------------------------------- 6. el token sirve para lo suyo
#
# Todo lo de arriba se hizo con la contraseña del admin, que puede con todo. Esto comprueba lo único
# que importa después: que el token guardado —con sus tres alcances y nada más— alcanza los issues
# del repositorio. Sin esta línea, un token mal formado no daría la cara hasta la primera consulta
# desde el MCP, que es donde peor se diagnostica.

con_token GET "/repos/$USUARIO/$REPO/issues?limit=1" >/dev/null \
    || morir "El token de token.env no puede leer los issues de $USUARIO/$REPO"
hecho "El token lee los issues de '$USUARIO/$REPO'"

# ----------------------------------------------------------------

printf '\n%sListo.%s  Web: %s   (usuario %s, contraseña en deploy/gitea/admin.env)\n' \
    "$C_VERDE" "$C_RESET" "$URL_LOCAL" "$USUARIO"
printf 'Issues: %s/%s/%s/issues\n' "$URL_LOCAL" "$USUARIO" "$REPO"
