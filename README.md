# Observatorio Kawsaypacha

Plataforma web de PREDES para monitorear y dar seguimiento a la **Gestión del Riesgo de Desastres (GRD)** y la **Adaptación al Cambio Climático (ACC)** en la región Cusco, Perú.

> **Estado actual:** Fase 0 — prototipo navegable para validación con stakeholders. Sin backend ni base de datos. Datos del Excel base + datos referenciales (mock).

## Estructura del repo

```
.
├── _specs/                     # especificaciones del producto
├── data/                       # Excel base (fuente original)
├── prototype/                  # app del prototipo (Vite + React + TS)
│   ├── public/data/            # JSON estáticos servidos por el front
│   ├── scripts/                # conversión Excel → JSON
│   ├── src/                    # código React
│   └── vercel.json             # config Vercel (rewrites SPA)
├── brainstorming.md            # notas iniciales
├── Claude.md                   # directivas del agente
└── README.md                   # este archivo
```

## Correr localmente

Requisitos: Node 20+ y npm.

```bash
cd prototype
npm install
npm run dev
```

Abre `http://localhost:5173`.

Para previsualizar el build de producción:

```bash
npm run build
npm run preview
```

## Regenerar los datos del Excel

Si actualizas `data/Base_Nivel Peligro_CCPP_Cusco.xlsx`, regenera los JSON:

```bash
# Requiere Python 3 con openpyxl: pip install openpyxl
python3 prototype/scripts/xlsx_to_json.py
```

Esto sobreescribe `prototype/public/data/ccpp.json` y `prototype/public/data/peligros.json`.

## Deploy a Vercel

El proyecto está configurado para que Vercel construya únicamente la carpeta `prototype/`.

### Paso a paso (primera vez)

1. Confirma que el código está pusheado al repo: `git@github.com:luis-huacho/Observatorio-Kawsaypacha.git`.
2. Entra a [vercel.com/new](https://vercel.com/new) (logueado con tu cuenta).
3. **Import Git Repository** → autoriza Vercel a leer tu repo si es la primera vez, luego selecciona `luis-huacho/Observatorio-Kawsaypacha`.
4. En la pantalla de configuración del proyecto:
   - **Framework Preset:** `Vite` (se detecta solo)
   - **Root Directory:** clic en *Edit* y selecciona **`prototype`** ← importante
   - **Build Command:** `npm run build` (default, OK)
   - **Output Directory:** `dist` (default, OK)
   - **Install Command:** `npm install` (default, OK)
5. Clic en **Deploy**. El primer build toma ~2-3 minutos.
6. Vercel te dará una URL tipo `observatorio-kawsaypacha.vercel.app`. Compártela con stakeholders.

### Builds posteriores

Cada `git push` a `master` dispara un nuevo deploy automático. PRs reciben URLs preview.

### Variables de entorno

**Ninguna por ahora.** No hay backend ni API keys. Cuando pasemos a Fase 1 (Django + Postgres) se agregarán aquí.

## Datos: real vs. referencial

| Dataset | Origen | Estado |
| --- | --- | --- |
| Centros poblados (8.968) | Excel SIGRID-CENEPRED + INEI | **Real** |
| Niveles de peligro (6.566 clasificaciones) | Excel SIGRID-CENEPRED | **Real** |
| Medidas (Ventana 2) | `medidas.mock.json` | **Referencial** |
| Inversión PPR 0068 (Ventana 3) | `inversion.mock.json` | **Referencial** |
| Prioridades multicriterio (Ventana 4) | `prioridades.mock.json` | **Referencial** |
| Normativa | `normativa.mock.json` | **Referencial** |

Todos los datos referenciales muestran un badge naranja **"Dato referencial"** en la UI y viven en archivos `*.mock.json` con flag `_mock: true` para poder eliminarlos limpiamente en Fase 1.

## Próximos pasos

Ver [`_specs/05-roadmap.md`](./_specs/05-roadmap.md). En resumen:

- **Fase 0 (actual):** prototipo navegable → validar con PREDES y stakeholders.
- **Fase 1:** Django + DRF + PostgreSQL + PostGIS en VPS, admin para editores.
- **Fase 2:** scrapers (MEF Consulta Amigable, SIGRID), flujo editorial, búsqueda full-text.
- **Fase 3:** generación de productos (ayudas memoria PDF), análisis y comparativas.

## Licencia y créditos

Operado por [PREDES](https://www.predes.org.pe/) — Centro de Estudios y Prevención de Desastres.

Fuentes de datos: SIGRID-CENEPRED, INEI, MEF, SENAMHI, INGEMMET, IGP, ANA, INAIGEM.
