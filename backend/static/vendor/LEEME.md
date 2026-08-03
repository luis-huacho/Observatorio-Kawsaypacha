# Copias locales de MapLibre y pmtiles

Estas copias las usa **el visor mínimo que el navegador headless captura para el mapa de la
ayuda memoria** (`templates/informes/mapa.html`), no el frontend público — ese trae sus propias
dependencias vía npm.

Van servidas por el backend y no desde un CDN porque el worker que genera el PDF puede estar en
un servidor sin salida a internet, y ahí una dependencia externa falla en silencio justo cuando
alguien necesita el documento.

Se les quitó el comentario `sourceMappingURL`: sin el `.map` al lado, `collectstatic` con
`CompressedManifestStaticFilesStorage` falla al no encontrarlo, y versionar 4 MB de sourcemaps
para depurar una librería de terceros no compensa.

Versiones (las mismas que `frontend/package.json`, para que el mapa del PDF y el del sitio se
comporten igual):

- maplibre-gl 4.7.1
- pmtiles 3.2.1

Para actualizarlas:

    cp frontend/node_modules/maplibre-gl/dist/maplibre-gl.js  backend/static/vendor/
    cp frontend/node_modules/maplibre-gl/dist/maplibre-gl.css backend/static/vendor/
    cp frontend/node_modules/pmtiles/dist/pmtiles.js          backend/static/vendor/
    # y volver a quitar la línea sourceMappingURL del .js
