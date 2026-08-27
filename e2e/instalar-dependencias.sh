#!/usr/bin/env bash
#
# instalar-dependencias.sh — deja la máquina lista para correr las pruebas E2E de Playwright.
#
# Uso:  ./e2e/instalar-dependencias.sh [--dry-run]
#       npm run e2e:preparar
#
# Instala las librerías de sistema que Chromium necesita, las dependencias de npm de la raíz y el
# navegador, y termina arrancándolo para comprobar que funciona de verdad.
#
# POR QUÉ EXISTE. La guía documentaba dos de los tres pasos: `npm install` y `playwright install
# chromium`. Faltaba el primero, y es el que rompe. En el despliegue del 04/08/2026 las 62 pruebas
# fallaron con
#
#     browserType.launch: Target page, context or browser has been closed
#     chrome-headless-shell: error while loading shared libraries: libatk-1.0.so.0
#
# que se lee como si el sitio estuviera caído, y no lo estaba. En Debian/Ubuntu el problema no se
# ve, porque `playwright install --with-deps` instala esos paquetes por su cuenta; en RHEL/Rocky/
# Fedora **no lo hace: Playwright solo sabe de apt**. De ahí la lista escrita a mano de más abajo.
#
# El propio Playwright lo dice al descargar, y conviene no alarmarse con el aviso:
#
#     BEWARE: your OS is not officially supported by Playwright;
#             downloading fallback build for ubuntu24.04-x64
#
# En la familia RHEL corre el binario compilado para Ubuntu, que funciona perfectamente **una vez
# están estas librerías**. Es justo la razón de que nadie las instale por ti.
#
# LO QUE NO HACE. No instala Docker ni Node: de eso se encarga la provisión del servidor (Docker,
# Node 22 por nvm, el usuario con sudo). Aquí solo se comprueban. Tampoco toca nada del
# despliegue —swap, `data/layers/`, los `.env`, los certificados—, que está en
# `_docs/despliegue.md`.
#
# NO CONFUNDIR con el Chromium del backend. La imagen del backend trae el suyo dentro
# (`backend/Dockerfile`), para el mapa de la ayuda memoria en PDF. Este es el del host, y solo
# sirve para las E2E.

set -Eeuo pipefail
IFS=$'\n\t'

DRY_RUN="no"

# Librerías de sistema de Chromium en la familia RHEL. La lista está **medida en un servidor**, no
# copiada de un foro: sale de `ldd` sobre el binario de Chromium de Playwright y `rpm -qf` sobre
# cada librería resuelta. dnf completa el resto de dependencias —cairo, fontconfig, libxcb,
# pixman, mesa-dri-drivers…— hasta unos 36 paquetes en una instalación mínima.
PAQUETES_RHEL=(
  alsa-lib atk at-spi2-atk at-spi2-core cups-libs
  libdrm libX11 libXcomposite libXdamage libXext libXfixes libXrandr libxkbcommon
  mesa-libgbm nspr nss pango
)

NODE_MINIMO=22

# ---------------------------------------------------------------------------
# Salida (mismos helpers que el script de provisión del servidor, que no está en este repositorio,
# para que los dos se lean igual)
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'; C_BLUE=$'\033[1;34m'; C_GREEN=$'\033[1;32m'
  C_YELLOW=$'\033[1;33m'; C_RED=$'\033[1;31m'; C_BOLD=$'\033[1m'
else
  C_RESET=""; C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BOLD=""
fi

log()  { printf '%s==>%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
ok()   { printf '%s  ok%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '%s  !!%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
err()  { printf '%serror%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; }

on_error() {
  local codigo=$? linea=${1:-?}
  err "Fallo en la línea $linea (código $codigo)."
  exit "$codigo"
}
trap 'on_error $LINENO' ERR

run() {
  if [[ "$DRY_RUN" == "yes" ]]; then
    local IFS=' '
    printf '%s  [dry-run]%s %s\n' "$C_YELLOW" "$C_RESET" "$*"
    return 0
  fi
  "$@"
}

usage() {
  cat <<EOF
instalar-dependencias.sh — deja la máquina lista para \`npx playwright test\`

Uso: ./e2e/instalar-dependencias.sh [opciones]

Opciones:
  --dry-run    Mostrar lo que se haría, sin cambiar nada
  -h, --help   Esta ayuda

Se ejecuta como usuario normal, NO con sudo (ver la comprobación al arrancar). Solo la
instalación de paquetes del sistema se eleva con sudo.

Da por hecho un servidor ya provisionado con Docker y Node $NODE_MINIMO; si falta algo, avisa y
no lo instala.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)  DRY_RUN="yes"; shift ;;
    -h|--help)  usage; exit 0 ;;
    *)          err "opción desconocida: $1"; usage; exit 2 ;;
  esac
done

# ---------------------------------------------------------------------------
# 1. Comprobaciones previas
# ---------------------------------------------------------------------------
comprobar_entorno() {
  printf '\n%s[1/4] Comprobaciones previas%s\n' "$C_BOLD" "$C_RESET"

  # Al revés que el script de provisión, este NO se corre como root, y no es un capricho:
  #   · nvm instala Node en el HOME del usuario, así que root no tiene `node` en el PATH.
  #   · Playwright guarda los navegadores en $HOME/.cache/ms-playwright. Con sudo acabarían en
  #     /root/.cache/, donde el usuario que corre las pruebas no los va a encontrar, y el error
  #     que se ve entonces es el mismo «browser has been closed» que este script viene a evitar.
  if [[ $EUID -eq 0 ]]; then
    err "No ejecutes este script como root ni con sudo."
    err "Node viene de nvm (que es por usuario) y los navegadores van a \$HOME/.cache/ms-playwright:"
    err "con sudo acabarían en /root y las pruebas seguirían fallando igual."
    err "Ejecútalo como tu usuario: ./e2e/instalar-dependencias.sh"
    exit 1
  fi

  if ! command -v sudo >/dev/null 2>&1; then
    err "Hace falta sudo para instalar los paquetes del sistema."
    exit 1
  fi

  if ! command -v node >/dev/null 2>&1; then
    err "No hay 'node' en el PATH. Este script no instala Node: lo hace la provisión del"
    err "servidor. Si usas nvm, abre una sesión de login o ejecuta 'nvm use $NODE_MINIMO'."
    exit 1
  fi

  local version mayor
  version="$(node -v)"          # vX.Y.Z
  mayor="${version#v}"; mayor="${mayor%%.*}"
  if (( mayor < NODE_MINIMO )); then
    err "Node $version es demasiado antiguo; el proyecto pide Node $NODE_MINIMO o superior."
    exit 1
  fi
  ok "node $version"

  command -v npm >/dev/null 2>&1 || { err "No hay 'npm' en el PATH."; exit 1; }
  ok "npm $(npm --version)"

  [[ "$DRY_RUN" == "yes" ]] && warn "Modo --dry-run: no se aplicará ningún cambio."
  return 0
}

# ---------------------------------------------------------------------------
# 2. Librerías de sistema de Chromium
# ---------------------------------------------------------------------------
instalar_librerias() {
  printf '\n%s[2/4] Librerías de sistema de Chromium%s\n' "$C_BOLD" "$C_RESET"

  local id="" id_like=""
  if [[ -r /etc/os-release ]]; then
    id="$(. /etc/os-release && echo "${ID:-}")"
    id_like="$(. /etc/os-release && echo "${ID_LIKE:-}")"
  fi

  case " $id $id_like " in
    *" rhel "*|*" fedora "*|*" centos "*)
      log "Familia RHEL detectada ($id): instalando la lista explícita con dnf."
      log "Playwright no sabe instalar dependencias fuera de apt, así que aquí van a mano."
      run sudo dnf install -y "${PAQUETES_RHEL[@]}"
      ok "paquetes del sistema listos"
      ;;
    *" debian "*|*" ubuntu "*)
      log "Familia Debian detectada ($id): lo resuelve el propio Playwright."
      # `--with-deps` instala los paquetes de apt Y descarga el navegador de una vez, así que en
      # esta rama el paso 3 no tiene que volver a bajarlo.
      run npx playwright install --with-deps chromium
      ok "paquetes del sistema y navegador listos"
      ;;
    *)
      warn "Distribución no reconocida (ID='$id', ID_LIKE='$id_like')."
      warn "No se instala nada: instala a mano las librerías de Chromium para tu sistema."
      warn "En la familia RHEL serían: ${PAQUETES_RHEL[*]}"
      ;;
  esac
}

# ---------------------------------------------------------------------------
# 3. Dependencias de npm y el navegador
# ---------------------------------------------------------------------------
instalar_playwright() {
  printf '\n%s[3/4] Playwright y el navegador%s\n' "$C_BOLD" "$C_RESET"

  local raiz
  raiz="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  log "Raíz del repositorio: $raiz"
  cd "$raiz"

  run npm install
  ok "dependencias de npm instaladas"

  # Solo Chromium: los dos proyectos de playwright.config.ts —escritorio (Desktop Chrome) y
  # movil (Pixel 5)— lo usan. Firefox y WebKit no hacen falta y son varios cientos de MB.
  # Es idempotente: si el navegador ya está en la versión que pide Playwright, no lo rebaja.
  run npx playwright install chromium
  ok "navegador Chromium listo"
}

# ---------------------------------------------------------------------------
# 4. La comprobación que da sentido al script
# ---------------------------------------------------------------------------
comprobar_navegador() {
  printf '\n%s[4/4] Comprobación: ¿arranca el navegador?%s\n' "$C_BOLD" "$C_RESET"

  if [[ "$DRY_RUN" == "yes" ]]; then
    printf '%s  [dry-run]%s lanzar Chromium para comprobar que arranca\n' "$C_YELLOW" "$C_RESET"
    return 0
  fi

  # Sin esto, la única forma de saber si falta una librería es correr la suite entera y leer mal el
  # resultado: el fallo aparece como «browser has been closed», que suena a que el sitio no
  # responde. Aquí sale en dos segundos y dice exactamente qué pasa.
  local salida
  if salida="$(node -e "
    require('playwright').chromium.launch()
      .then(async b => { console.log(b.version()); await b.close(); })
      .catch(e => { console.error(e.message.split('\n').filter(Boolean).slice(0, 3).join(' | ')); process.exit(1); })
  " 2>&1)"; then
    ok "Chromium arranca (versión $salida)"
  else
    err "Chromium no arranca:"
    err "  $salida"
    err "Si menciona una librería .so que falta, añádela a PAQUETES_RHEL en este script."
    exit 1
  fi
}

resumen() {
  printf '\n%sListo.%s Las pruebas E2E corren contra un sitio YA levantado y sembrado:\n\n' \
    "$C_GREEN$C_BOLD" "$C_RESET"
  printf '  E2E_URL=https://<dominio> npx playwright test\n\n'
  printf 'Ver _specs/08-plan-pruebas.md y el docblock de playwright.config.ts.\n\n'
}

main() {
  comprobar_entorno
  instalar_librerias
  instalar_playwright
  comprobar_navegador
  [[ "$DRY_RUN" == "yes" ]] || resumen
}

main
