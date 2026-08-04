# Cabeceras de seguridad. Están en su propio archivo, y no dentro de `ssl-comun.inc`, porque hay
# que repetirlas en cada `location` que declare un `add_header` propio.
#
# El motivo es una regla de nginx que sorprende a todo el mundo una vez: **`add_header` no se
# hereda por acumulación**. En cuanto un bloque declara uno, se descartan TODOS los del nivel
# superior. Como `/assets/`, `= /index.html`, `/static/`, `/media/` y `/tiles/` declaran su
# `Cache-Control` o sus cabeceras CORS, se quedaban sin estas tres —el bundle de JavaScript sin
# `nosniff` y la portada sin HSTS— aunque `ssl-comun.inc` las pusiera a nivel `server`.
#
# Medido el 04/08/2026 contra el sitio ya desplegado: el dominio de la SPA no devolvía ninguna de
# las tres. Ver E-005 en _specs/09-errores.md.
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
