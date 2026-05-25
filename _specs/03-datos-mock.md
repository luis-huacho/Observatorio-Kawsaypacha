# 03 — Datos: Reales (Excel) y Mock

## Datos reales: el Excel base

**Archivo:** `data/Base_Nivel Peligro_CCPP_Cusco.xlsx`

**Estructura:** 9 hojas, una por tipo de peligro.

| Hoja | Peligro |
| --- | --- |
| `Sismo` | Sismo |
| `Friaje` | Friaje |
| `Inundación` | Inundación |
| `Heladas` | Heladas |
| `Bajas temperaturas` | Bajas temperaturas |
| `Lluvias` | Lluvias intensas |
| `Sequía` | Sequía |
| `Incendios Forestales` | Incendios forestales |
| `Movimientos en masa` | Movimientos en masa |

**Esquema por hoja** (mismas columnas):

| Columna | Tipo | Notas |
| --- | --- | --- |
| `DEPARTAMEN` | str | Siempre "CUSCO" |
| `PROVINCIA` | str | 13 provincias |
| `DISTRITO` | str | |
| `CODIGO` | str (10 dígitos) | Código INEI de CCPP — clave única |
| `NOMB_CPOB` | str | Nombre del centro poblado |
| `CATEGORIA` | str | CIUDAD, PUEBLO, ANEXO, CASERIO, etc. |
| `ALTITUD` | int | msnm |
| `LONGITUD` | float | grados decimales (negativo) |
| `LATITUD` | float | grados decimales (negativo) |
| `POBLACION` | int | INEI |
| `PELIGRO` | str \| null | Nombre del peligro si el CCPP tiene clasificación |
| `TIP_PELIG` | str \| null | Subtipo (ej. "Geodinamica interna") |
| `NIVEL_PELI` | int (1-4) \| null | 1=bajo, 4=extremo. Nulo si no clasificado |
| `Fuente` | str \| null | Ej. "SIGRID_CENEPRED" |
| `Link` | str (URL) \| null | Enlace a la fuente |

**Sparsity importante:** la gran mayoría de CCPP **no tienen** nivel asignado en cada hoja. Por ejemplo, en Sismo solo unos cientos de los 8.969 CCPP tienen `NIVEL_PELI` no nulo. La UI debe manejar esto: "Sin dato clasificado" como estado válido y diferenciado de "Nivel bajo".

## Script de conversión

`prototype/scripts/xlsx-to-json.ts` — corre **una vez** (o cuando se actualiza el Excel). Produce dos JSON normalizados:

### `public/data/ccpp.json`

Lista canónica de centros poblados (deduplicada por `CODIGO`). Se construye uniendo todas las hojas y tomando los campos invariantes.

```json
[
  {
    "codigo": "0801010001",
    "nombre": "CUSCO",
    "categoria": "CIUDAD",
    "departamento": "CUSCO",
    "provincia": "CUSCO",
    "distrito": "CUSCO",
    "ubigeo_distrito": "080101",
    "lat": -13.51927548,
    "lon": -71.97675606,
    "altitud": 3439,
    "poblacion": 111930
  }
]
```

### `public/data/peligros.json`

Tabla larga (long format) de clasificaciones de peligro por CCPP × tipo. Solo filas con `NIVEL_PELI` no nulo.

```json
[
  {
    "codigo_ccpp": "0801010001",
    "peligro": "Sismo",
    "tipo": "Geodinamica interna",
    "nivel": 4,
    "fuente": "SIGRID_CENEPRED",
    "fuente_url": "https://n9.cl/lic6j"
  }
]
```

### Geometrías administrativas

Para mapas coropléticos de distritos/provincias necesitamos GeoJSON de los límites. Fuentes posibles (descarga manual una vez, guardar en `public/data/geo/`):
- INEI — shapefile de distritos (convertir a GeoJSON simplificado con mapshaper)
- humdata.org / data.humdata.org — Perú admin boundaries

**Archivos esperados:**
- `public/data/geo/cusco-provincias.geojson`
- `public/data/geo/cusco-distritos.geojson`

Simplificación recomendada: tolerancia 0.001° para mantener el archivo bajo ~500 KB.

## Datos mock

Convención: **todo archivo mock termina en `.mock.json`** y todo registro mock lleva el campo `_mock: true`. Esto permite:

1. Buscar `*.mock.json` para inventariar la deuda de datos.
2. Filtrar por `_mock` en runtime para mostrar el badge.
3. Eliminar de un grep + un find en fase 1.

### `public/data/medidas.mock.json` (Ventana 2)

```json
[
  {
    "_mock": true,
    "id": "qochas-pampallacta",
    "titulo": "Qochas comunales en Pampallacta",
    "peligro": "Sequía",
    "ambito": "comunal",
    "resultado": "exito",
    "ubigeo": "080302",
    "comunidad": "Pampallacta",
    "resumen_corto": "Construcción de 12 qochas que abastecen riego en época seca.",
    "video_url": null,
    "imagen": "/data/imagenes/mock-qochas.jpg",
    "tags": ["Sequía", "Siembra de agua", "Comunal"]
  }
]
```

### `public/data/inversion.mock.json` (Ventana 3)

Mock plausible basado en estructura PPR 0068 / Consulta Amigable MEF.

```json
{
  "_mock": true,
  "anio": 2025,
  "agregados": {
    "pim_total": 145000000,
    "ejecutado": 78000000,
    "porcentaje_ejecucion": 0.538,
    "municipios_con_ppr_0068": 87
  },
  "por_distrito": [
    {
      "ubigeo": "080302",
      "distrito": "Pisac",
      "provincia": "Calca",
      "pia": 1200000,
      "pim": 1450000,
      "devengado": 890000,
      "pct_prevencion": 0.62,
      "pct_respuesta": 0.38
    }
  ],
  "comparacion_prevencion_respuesta": {
    "prevencion_total": 52000000,
    "respuesta_total": 26000000
  }
}
```

### `public/data/prioridades.mock.json` (Ventana 4)

```json
{
  "_mock": true,
  "metodologia": "Promedio ponderado normalizado de 6 variables (exposición, población expuesta, pobreza, infraestructura, agua, frecuencia).",
  "pesos_default": {
    "exposicion": 0.25,
    "poblacion_expuesta": 0.20,
    "pobreza": 0.15,
    "infraestructura": 0.15,
    "agua": 0.15,
    "frecuencia": 0.10
  },
  "scores": [
    {
      "ubigeo": "080302",
      "distrito": "Pisac",
      "score": 0.78,
      "nivel": "alto",
      "variables": {
        "exposicion": 0.8, "poblacion_expuesta": 0.65,
        "pobreza": 0.7, "infraestructura": 0.6,
        "agua": 0.55, "frecuencia": 0.85
      }
    }
  ]
}
```

### `public/data/normativa.mock.json`

```json
[
  {
    "_mock": true,
    "id": "ley-29664",
    "titulo": "Ley 29664 — Sistema Nacional de Gestión del Riesgo de Desastres (SINAGERD)",
    "tipo": "Ley",
    "fecha": "2011-02-19",
    "ambito": "nacional",
    "resumen": "Crea el SINAGERD y define los procesos de la GRD.",
    "url_oficial": "https://...",
    "analisis_predes": null
  }
]
```

## Cómo se elimina la data mock en fase 1

Cuando un dataset se reemplace por backend real:

1. Borrar el archivo `*.mock.json` correspondiente.
2. Reemplazar el fetch en el componente por la llamada al API.
3. Verificar que ya no aparezcan `<MockBadge />` asociados (deben venir del flag `_mock` que ya no existe).

Test de regresión: un script `pnpm check:no-mocks` que falla si quedan `.mock.json` referenciados.

## Imágenes y multimedia mock

Carpeta `prototype/public/data/imagenes/` con imágenes libres de derechos (Unsplash, Pexels) **de Andes peruanos**. Nombrar con prefijo `mock-` para limpiar después.

---

**Documentos relacionados:** [[01-prototipo-fase0]], [[02-navegacion-ux]], [[04-arquitectura-fase1]]
