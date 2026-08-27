# 10 — Pipeline CI/CD

Cómo llega el código al servidor, en qué orden y qué se comprueba (ADR-A21). Desde el **27/08/2026** cada push a `master` en Bitbucket redespliega el entorno de QA; antes de esa fecha el despliegue era una cadena de comandos que había que recordar entera.

Este documento manda sobre **el orden y las reglas**. Los comandos pegables están en [`_docs/despliegue.md`](../_docs/despliegue.md), la infraestructura en [07-despliegue-ops.md](07-despliegue-ops.md) y lo que se prueba en [08-plan-pruebas.md](08-plan-pruebas.md). Si una línea de aquí es un comando, tiene que existir igual en alguno de esos: de lo contrario sobra aquí o falta allí.

## Las dos vías, y por qué son la misma

| Vía | Quién la lanza | Qué ejecuta |
|---|---|---|
| **Automática** | Push a `master` en Bitbucket | `bitbucket-pipelines.yml`: comprueba tipos → `ssh` al servidor → `deploy/desplegar.sh` |
| **Manual** | Una persona, en el servidor | `./deploy/desplegar.sh` |

**El pipeline no es un procedimiento paralelo: solo es quien llama.** Todo el procedimiento vive en `deploy/desplegar.sh`, versionado, y el YAML no lleva lógica a propósito. La regla, escrita en el propio script: **si no sirve desde una terminal, no sirve**. Eso es lo que impide que el despliegue automático y el manual se separen en dos procedimientos que divergen — que es exactamente lo que le pasó al runbook duplicado que 07 tuvo hasta esta rama.

## Qué comprueba el CI, y qué no

El paso de integración es uno solo: `npm ci && npm run lint` en `frontend/`, o sea **`tsc --noEmit`**. Corre sin Docker y corta los errores de tipos antes de que lleguen al bundle, que es lo único que sale barato comprobar desde fuera del servidor.

**No corre `pytest` ni Playwright, y es deliberado.** `pytest` se ejecuta dentro del contenedor para usar las mismas versiones de GDAL, tippecanoe y WeasyPrint que producción, y la corrida E2E que vale es la que ataca a nginx con el stack entero levantado: las dos exigen el servidor, no un runner. La suite sigue lanzándose a mano (08).

> **Un check verde de Pipelines no dice que las pruebas pasaron. Dice que el frontend compila.** Escrito aquí porque la confusión contraria es gratuita y cara.

En los *pull requests* corre solo el paso de tipos: se comprueba, no se despliega.

## Las siete etapas de `desplegar.sh`

| # | Etapa | La invariante que fija |
|---|---|---|
| 1 | Árbol limpio | Aborta si hay cambios versionados sin commitear. Un despliegue no es el momento de descubrir trabajo a medias, y así lo editado en el servidor **bloquea** el siguiente despliegue en vez de perderse |
| 2 | Traer la versión | `git pull --ff-only`: si la historia divergió, falla en vez de fabricar en el servidor un merge que no está en Bitbucket y que nadie vería nunca |
| 3 | Construir | `build backend worker frontend`. **`worker` es imagen aparte**: sin reconstruirlo, la cola seguiría corriendo el código viejo |
| 4 | Publicar y sellar | `run --rm frontend` copia el `dist` al volumen que sirve nginx, y **después** se escribe el SHA en `/version.txt` — el `CMD` del servicio empieza por `rm -rf /out/*` y un sello anterior se lo llevaría por delante |
| 5 | Recargar nginx | `nginx -t` **antes** del `-s reload`. `reload` **devuelve 0 aunque la configuración esté rota**: solo manda la señal, y el maestro la rechaza por su cuenta escribiendo el error en su propio log. Sin el test, un error de sintaxis pasa el despliegue en verde dejando nginx con la configuración anterior |
| 6 | Esperar salud | Hasta 210 s a que el contenedor `backend` esté `healthy` (su `start_period` es de 90 s: migraciones y `meili_setup` corren en el arranque) |
| 7 | Verificar desde fuera | Pide `https://$SITE_DOMAIN/version.txt` y lo compara con el SHA desplegado. Si no coincide, **el despliegue falla**. Después, `comprobar-sitio.sh` con ese mismo SHA |

## Por qué el despliegue se verifica a sí mismo

**Un despliegue a medias se ve idéntico a uno correcto.** El 27/08/2026 el sitio sirvió durante dieciséis días el bundle del 11/08: la SPA respondía 200, el API 200, los siete contenedores `healthy`, el `index.html` con `last-modified` de ese mismo día y cero errores en los logs de nginx, del backend y del worker. La única forma de verlo era abrir el bundle y buscar dentro un texto que se había cambiado.

La causa fue trivial —`up -d` sin `--build`, y el servicio `frontend` es de un disparo: vuelve a copiar *su* `dist`, que era el viejo—. Lo que no es trivial es que **ninguna comprobación de las que se hacían podía distinguirlo**. `deploy/comprobar-sitio.sh` ya declaraba ese punto ciego en su cabecera desde que se escribió —«que nginx conteste pero sirva el bundle equivocado»— y no lo cubría.

De ahí el sello: `/version.txt` viaja **dentro del propio `dist`**, así que responde por lo que el sitio sirve de verdad y no por lo que el pipeline cree haber desplegado. Se consulta en cualquier momento:

```bash
curl -s https://observatorio.somosiadigital.com/version.txt   # el SHA que está arriba de verdad
```

`comprobar-sitio.sh` lo acepta como cuarto argumento; sin él informa del SHA servido sin juzgarlo, que es lo que quiere un cron desde otra máquina —no sabe qué commit debería estar arriba—.

## Por qué el build ocurre en el servidor

La imagen del backend compila **tippecanoe desde el código fuente** e instala Chromium: construirla en Pipelines sin caché de capas costaría mucho más de lo que ahorra, y obligaría además a montar un registry. Así el pipeline gasta ~1 min por despliegue y no necesita ninguno.

La salida, si algún día el build en el servidor molesta, es **Pipelines + registry**, y `deploy/desplegar.sh` no cambia: seguiría siendo quien despliega.

## El remoto que dispara el despliegue

**El pipeline vive en Bitbucket, o sea en `drinux`.** `git push` a secas solo alcanza `origin` (GitHub), que no despliega nada y no avisa de que no lo hizo. El push va siempre a los dos:

```bash
git push origin master && git push drinux master
```

Es la misma regla que mantiene espejados los dos remotos, con una consecuencia nueva: desde el 27/08, olvidar `drinux` ya no solo deja al cliente atrás — deja también el entorno sin desplegar.

## Qué despliega, y qué no

**Solo el entorno de QA** (`observatorio.somosiadigital.com`). Producción de PREDES no está enganchada al pipeline; cuando lo esté, lo que hay que repetir es la configuración de una vez que describe [`_docs/despliegue-entorno-desarrollo.md`](../_docs/despliegue-entorno-desarrollo.md), no el script.

Y **en local no aplica**: la etapa 7 verifica por HTTPS contra `SITE_DOMAIN`. El día a día en local son `compose.dev.yml` (código montado, Vite en el host) y `compose.local.yml` (el bundle servido por nginx sobre HTTP) — ver 07.

## Lo que no se puede versionar

Tres cosas viven fuera del repositorio porque son credenciales o son de la máquina: el par de claves SSH y el *known host* en *Repository settings*, las variables `DESPLIEGUE_HOST` y `DESPLIEGUE_USUARIO`, y la clave pública en `~/.ssh/authorized_keys` del servidor.

Esa última **va restringida con `command=`**, y es lo que hace aceptable la superficie que abre el pipeline: una clave SSH viva en la nube de Atlassian con acceso a la máquina. Con `command=` esa clave **no da shell**, ni túneles, ni agente — lo único que puede hacer es redesplegar `master`. El comando que manda el pipeline es solo un disparador; el que se ejecuta lo fija el servidor. Sin `command=`, quien tuviera la clave tendría el servidor, y con él la base, los certificados y el `.env`.

El literal exacto está en `_docs/despliegue-entorno-desarrollo.md`; no se copia aquí para que exista en un solo sitio.

## Qué sigue siendo manual

Que haya pipeline no significa que todo esté automatizado. Sigue dependiendo de una persona:

| Qué | Dónde |
|---|---|
| La suite completa (`pytest`, `-m lento`, `lint`, `build`, Playwright dos veces) | 08 |
| Las cinco comprobaciones previas a la entrega | 08 |
| La carga y el reemplazo de datos (`seed`, `DatasetUpload`) | `_docs/despliegue.md` |
| Las seis tareas de cron del anfitrión — **se instalan a mano en cada servidor y nada comprueba que estén puestas** | `_docs/despliegue.md` |
| El reinicio del worker, que **nunca es automático** a propósito | 07 |
| El despliegue a producción PREDES | `_docs/despliegue.md` |

## Qué no está en este documento

| Busca | Está en |
|---|---|
| Servicios, composes, nginx, variables, volúmenes | [07-despliegue-ops.md](07-despliegue-ops.md) |
| Puesta en marcha, carga de datos, backups, diagnóstico | [`_docs/despliegue.md`](../_docs/despliegue.md) |
| El incidente del 27/08 contado entero | La bitácora de [README.md](README.md) |
| Qué se prueba y con qué | [08-plan-pruebas.md](08-plan-pruebas.md) |
| La deuda que deja esta decisión | [`_docs/deuda-tecnica.md`](../_docs/deuda-tecnica.md) |
| Lo que está roto ahora mismo | El tracker (ver [09-errores.md](09-errores.md)) |
