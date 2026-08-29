# Compila la SPA y deja dist/ en /out para que compose lo copie al volumen web_dist.
#
# Vite **hornea las variables VITE_* en el bundle durante el build**, no las lee en runtime. Si
# no llegan aquí, la imagen de producción sale apuntando a localhost y el sitio queda mudo en el
# servidor sin un solo error en los logs. Por eso son build args obligatorios: mejor que el build
# falle que un despliegue silenciosamente roto.
FROM node:22-alpine AS build

ARG VITE_API_URL
ARG VITE_SEARCH_URL
ARG VITE_TILES_URL
ARG VITE_MEILI_SEARCH_KEY
ARG VITE_CARTO_KEY

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# `.env` no llega aquí (ver .dockerignore): los valores vienen de los build args, para que la
# imagen no herede por accidente la configuración de la máquina de quien construye.
RUN test -n "$VITE_API_URL" || (echo "ERROR: falta el build arg VITE_API_URL" && exit 1)
RUN printf '%s\n' \
      "VITE_API_URL=$VITE_API_URL" \
      "VITE_SEARCH_URL=$VITE_SEARCH_URL" \
      "VITE_TILES_URL=$VITE_TILES_URL" \
      "VITE_MEILI_SEARCH_KEY=$VITE_MEILI_SEARCH_KEY" \
      "VITE_CARTO_KEY=$VITE_CARTO_KEY" \
    > .env.production
RUN npm run build

FROM alpine:3.20
COPY --from=build /app/dist /srv/dist
# El servicio en compose monta el volumen web_dist en /out y ejecuta este comando. El `rm` va
# antes del `cp` para que un despliegue no deje conviviendo los assets viejos con los nuevos:
# tienen hash en el nombre, así que se acumularían indefinidamente.
CMD ["sh", "-c", "rm -rf /out/* && cp -r /srv/dist/. /out/ && echo 'dist publicado en el volumen'"]
