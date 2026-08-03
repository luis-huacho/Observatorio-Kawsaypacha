# 08 — Plan de pruebas

Qué se prueba, con qué, y cuándo se considera que la plataforma está lista para entregar. La regla que ordena el documento: **cada caso de prueba obligatorio nace de una anomalía verificada en los datos reales o de una decisión de arquitectura que se puede romper en silencio**. No se persigue cobertura por cobertura.

## Herramientas

| Nivel | Herramienta | Dónde | Qué cubre |
|---|---|---|---|
| Unitario / integración | **pytest + pytest-django** | `backend/tests/` | Importadores, contrato del API, flujo editorial, seed, emisor de tiles |
| Extremo a extremo | **Playwright** | `e2e/` | Las rutas críticas en navegador real contra el stack de compose |
| Tipos y build | `tsc --noEmit` + `vite build` | `frontend/` | Que el frontend compila antes de cada commit |

Comandos:

```bash
docker compose exec backend pytest              # suite backend
docker compose exec backend pytest -m lento     # incluye los Excel completos (lenta)
cd frontend && npm run lint && npm run build    # tipos + build
npx playwright test                             # E2E contra el stack levantado
```

## Datos de prueba

Los Excel reales pesan 5.4 MB y tardan; las pruebas usan **muestras reducidas** en `backend/tests/fixtures/`, construidas a mano para que cada anomalía conocida esté representada:

| Archivo | Contenido |
|---|---|
| `nivel_peligro_muestra.xlsx` | 3 hojas (`Sismo`, `Lluvias`, `Incendios Forestales`) × ~50 filas: incluye SICUANI con `DISTRITO` vacío en una hoja, filas sin `NIVEL_PELI`, 2 filas huérfanas sin `CODIGO`, y las dos grafías de `Fuente` |
| `frecuencia_muestra.xlsx` | Hoja `NºEMERGENCIAS` con OLLANTAYTAMBO (desglose normal), CUSCO (solo `TOT_*`), SANGARARÁ (descuadre), y sin la fila de ACOMAYO |

La prueba contra los archivos completos existe pero va marcada `@pytest.mark.lento` y queda fuera de la corrida por defecto.

## Casos obligatorios — backend

### `test_importadores.py`

Salen de la auditoría del 02/08 documentada en 01 y 03. Cada uno protege una decisión que un refactor puede deshacer sin que nada falle a la vista:

1. **ADR-D1**: CUSCO (080101) se importa en `TotalDeclaradoEmergencias` con `total=134` y **no** genera filas de `FrecuenciaEmergencia`. Es el caso que motivó el ADR: recalcular desde el desglose deja la capital regional en cero.
2. El nombre del peligro sale de la columna `PELIGRO`, no del título de la hoja: la hoja `Lluvias` produce `TipoPeligro(nombre="Lluvias intensas", slug="lluvias_intensas")`.
3. **Slugs con guion bajo**: ningún `TipoPeligro.slug` contiene `-`. Es la clave de las propiedades `nivel_<slug>` del tile; con guion el mapa deja de pintar y ninguna otra prueba lo nota.
4. Filas con `PELIGRO` pero sin `NIVEL_PELI` se descartan y quedan contadas en el `log`; no se asume nivel 1.
5. Filas sin `CODIGO` se descartan con aviso.
6. Al deduplicar CCPP entre hojas se prefiere el valor no vacío: SICUANI conserva su distrito.
7. `CENEPRED_SIGRID` se normaliza a `SIGRID_CENEPRED`.
8. Descuadre entre subtotal y desglose (SANGARARÁ): prevalece el desglose y la diferencia queda en el `log`.
9. Distrito del padrón sin fila en el Excel (ACOMAYO): aviso en el `log`, la importación no aborta.
10. **Todo-o-nada**: un Excel con una hoja corrupta deja los datos activos previos intactos y el `DatasetUpload` en `error`.
11. Reimportar reemplaza en vez de duplicar: dos importaciones seguidas del mismo archivo dan los mismos conteos.

### `test_api_*.py`

Un módulo por familia de endpoints. El criterio es el **contrato del spec 02**, no la implementación:

- Forma exacta del payload de `/api/ccpp/{codigo}/`, `/api/peligros/resumen/` y `/api/peligros/frecuencia/` (claves y anidamiento, comparados contra los ejemplos del spec).
- `desglose_disponible: false` y `solo_total: true` para CUSCO; `true`/`false` para OLLANTAYTAMBO.
- **404 para ACOMAYO** (sin fila) frente a `total: 0` para un distrito con fila y sin emergencias. Son dos estados vacíos distintos y la UI los distingue.
- `clasificaciones: []` para un CCPP sin clasificar — "sin dato" no es "nivel bajo".
- Solo se sirve `estado=publicado`: un objeto en borrador o en revisión no aparece en listado, detalle ni export.
- Paginación (`page_size` default 50, máximo 200) y filtros de cada endpoint.
- Exports `.xlsx`: cabeceras correctas, y respetan los mismos filtros que la lista.
- Throttling de exports y PDF (`30/hour`).
- `/api/inversion/` responde `{"disponible": false}` mientras no haya datos.
- `/api/sitio/` trae config, bloques, menú y hero, y omite los `EnlaceMenu` con `visible=False` (Prioridades).
- `imagen_portada` llega **resuelta** por el serializer cuando el campo está vacío: la regla del default institucional vive en el backend y ningún cliente la replica.

### `test_workflow.py`

- Transiciones válidas e inválidas de `WorkflowMixin.transicionar()` (`borrador → publicado` directo debe fallar).
- Cada transición encola su correo con el destinatario correcto: a revisión → grupo Publicadores; publicado → autor; devuelto → autor con `nota_revision`.
- `publicado_en` se sella al publicar.
- Un usuario sin permiso `puede_publicar` no ve la acción de publicar en el admin.

### `test_seed.py`

Conteos canónicos tras `manage.py seed` sobre los Excel reales (marcado `lento`): **8,968 CCPP · 10,978 clasificaciones · 13 provincias · 112 distritos · 111 distritos con frecuencia**. Si un refactor del importador pierde filas, esta prueba es la que lo dice.

### `test_tiles.py`

- El emisor de GeoJSONSeq **omite** las claves `nivel_*` ausentes en vez de escribir `null` (es lo que mantiene el tile en 2.7 MB y "sin dato" como categoría propia).
- Las claves emitidas coinciden exactamente con los slugs de `TipoPeligro`.
- `nivel_max` es el máximo de los niveles presentes.

## Casos obligatorios — E2E (Playwright)

Corren contra el stack de compose ya sembrado. Cubren lo que las pruebas de API no ven: que el mapa pinte y que los filtros lleguen a la pantalla.

| Spec | Comprueba |
|---|---|
| `peligros.spec.ts` | El mapa carga y dibuja los CCPP · cambiar de peligro repinta el semáforo · el filtro por nivel mínimo reduce los puntos · el popup abre la ficha del CCPP · el selector de mapa base conmuta · la ayuda memoria descarga un PDF |
| `home.spec.ts` | Las cifras salen del API (no de un mock) · el bloque de actualidad lista noticias y normas con sus enlaces |
| `buscar.spec.ts` | Una búsqueda devuelve resultados agrupados por tipo · con Meilisearch caído el fallback DRF sigue respondiendo |
| `medidas.spec.ts` | Las facetas muestran conteos y filtran · el detalle abre con su galería |
| `inversion.spec.ts` | Se muestra el estado vacío "información en preparación", no un cero ni un gráfico en blanco |

## Comprobaciones manuales (previas a la entrega)

Automatizarlas no sale a cuenta, pero omitirlas sí:

1. **Restauración de backup**: compose limpio + `psql < dump` + `meili_rebuild` + visor OK. Se cronometra y el tiempo se documenta en `_docs/despliegue.md`. El TDR pide backups; un backup no probado no es un backup.
2. **Ciclo completo de administración**, tal como lo hará PREDES: subir el Excel → ver el cambio en el visor → crear una medida → enviarla a revisión → publicarla → verla en el sitio.
3. **Reemplazo de una capa cartográfica** y regeneración de tiles desde el admin.
4. **Impresión de la ayuda memoria** en vista previa de impresión, no solo la descarga.
5. **Responsive y accesibilidad** en las rutas principales (criterios de `archive/02-navegacion-ux.md`).

## Criterio de "listo para entregar"

- `pytest` completo (incluido `-m lento`) en verde.
- `npm run lint && npm run build` sin errores.
- `npx playwright test` en verde contra el stack de producción local.
- Las cinco comprobaciones manuales hechas y documentadas.
- Los conteos canónicos verificados sobre la base de producción tras el seed real.
