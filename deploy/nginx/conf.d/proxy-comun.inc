# Cabeceras que Django necesita para saber quién pregunta y por qué esquema.
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
# Sin esto, con SECURE_PROXY_SSL_HEADER activo Django cree que la petición es HTTP y redirige
# en bucle.
proxy_set_header X-Forwarded-Proto $scheme;
proxy_http_version 1.1;
proxy_set_header Connection "";
