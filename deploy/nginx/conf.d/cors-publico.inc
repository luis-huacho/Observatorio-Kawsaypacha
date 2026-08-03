# CORS para el dominio de la SPA (ADR-A14). Los estáticos los sirve nginx, así que
# django-cors-headers no los ve: estas cabeceras tienen que estar aquí.
add_header Access-Control-Allow-Origin "https://observatorio.predes.org.pe" always;
add_header Vary "Origin" always;
