# Parámetros TLS compartidos por los dos dominios.
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 1d;
ssl_stapling on;
ssl_stapling_verify on;

# Las cabeceras de seguridad viven en `seguridad-comun.inc`, que este archivo incluye y que además
# hay que repetir en cada `location` con `add_header` propio (ahí se explica por qué).
include /etc/nginx/conf.d/seguridad-comun.inc;
