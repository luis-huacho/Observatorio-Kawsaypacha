#!/bin/sh
# Recarga nginx cada 6 h para que tome el certificado que certbot haya renovado por debajo.
#
# Sin esto, el contenedor `certbot` renueva sobre el día 60 y nginx sigue presentando el
# certificado viejo hasta que caduca el 90, cuando el sitio se cae con NET::ERR_CERT_DATE_INVALID
# en todos los navegadores. `compose.yaml` y `_specs/07-despliegue-ops.md` daban esta recarga por
# hecha desde el principio; lo que faltaba era implementarla.
#
# Por qué es un script de /docker-entrypoint.d/ y no un `command:` en compose, que es la receta
# habitual: el /docker-entrypoint.sh de la imagen solo ejecuta estos scripts —envsubst incluido—
# `if [ "$1" = "nginx" ]`. Un `command` que empiece por `sh` se salta la generación de las
# plantillas de deploy/nginx/templates/, y nginx arrancaría sin los fragmentos con los dominios.
#
# El entrypoint ejecuta este script de forma síncrona, antes de arrancar nginx, así que el bucle
# va al fondo. El primer `reload` llega a las 6 h, con el maestro ya en marcha. Un `reload` con la
# configuración rota falla y deja el proceso viejo sirviendo: es seguro.

set -eu

(
    while :; do
        sleep 6h
        nginx -s reload 2>&1 || echo "$0: el reload falló; nginx sigue con la configuración anterior"
    done
) &
