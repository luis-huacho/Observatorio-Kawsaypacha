# Compila la SPA y deja dist/ en /out para que compose lo copie al volumen web_dist.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM alpine:3.20
COPY --from=build /app/dist /srv/dist
# El servicio en compose monta el volumen web_dist en /out y ejecuta este comando.
CMD ["sh", "-c", "rm -rf /out/* && cp -r /srv/dist/. /out/"]
