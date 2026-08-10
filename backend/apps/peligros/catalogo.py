"""Catálogo canónico de peligros y eventos.

Fuente única de verdad para el importador, las fixtures y el emisor de tiles. Existe como
módulo y no solo como fixture porque el importador necesita mapear **hoja del Excel → peligro**
antes de tocar la base: el nombre de la hoja no es el nombre del peligro (`Lluvias` →
`Lluvias intensas`, `Incendios Forestales` → `Incendios forestales`), y derivar el slug con
`slugify()` produciría guion medio, que rompe la clave `nivel_<slug>` de los tiles.

Verificado contra los archivos reales el 02/08/2026 (ver 01-modelo-datos.md).
"""

# hoja del Excel → (nombre del peligro, slug, categoria_geo, orden)
#
# `icono` es un nombre de la librería lucide en kebab-case. Viaja por el API para que el
# visor no tenga que conocer los peligros: el símbolo del mapa codifica el **tipo** con la
# forma del ícono y el **nivel** con el color, así que añadir un peligro en el admin no
# obliga a tocar el frontend. `color` ya no pinta esos símbolos —lo hace el nivel— y queda
# para las piezas donde el peligro es la única dimensión (chips, gráficos por tipo).
PELIGROS: list[dict] = [
    {"hoja": "Sismo", "nombre": "Sismo", "slug": "sismo",
     "categoria_geo": "Geodinamica interna", "orden": 1, "color": "#8b5cf6",
     "icono": "activity"},
    {"hoja": "Heladas", "nombre": "Heladas", "slug": "heladas",
     "categoria_geo": "Metereologicas", "orden": 2, "color": "#38bdf8",
     "icono": "snowflake"},
    {"hoja": "Bajas temperaturas", "nombre": "Bajas temperaturas", "slug": "bajas_temperaturas",
     "categoria_geo": "Metereologicas", "orden": 3, "color": "#0ea5e9",
     "icono": "thermometer-snowflake"},
    {"hoja": "Friaje", "nombre": "Friaje", "slug": "friaje",
     "categoria_geo": "Metereologicas", "orden": 4, "color": "#22d3ee",
     "icono": "wind"},
    {"hoja": "Sequía", "nombre": "Sequía", "slug": "sequia",
     "categoria_geo": "Metereologicas", "orden": 5, "color": "#f59e0b",
     "icono": "sun-dim"},
    # La hoja se llama "Lluvias"; la columna PELIGRO dice "Lluvias intensas".
    {"hoja": "Lluvias", "nombre": "Lluvias intensas", "slug": "lluvias_intensas",
     "categoria_geo": "Metereologicas", "orden": 6, "color": "#3b82f6",
     "icono": "cloud-rain"},
    {"hoja": "Inundación", "nombre": "Inundación", "slug": "inundacion",
     "categoria_geo": "Metereologicas", "orden": 7, "color": "#2563eb",
     "icono": "waves"},
    # La hoja se llama "Incendios Forestales" (F mayúscula); PELIGRO dice "Incendios forestales".
    {"hoja": "Incendios Forestales", "nombre": "Incendios forestales",
     "slug": "incendios_forestales", "categoria_geo": "Metereologicas", "orden": 8,
     "color": "#ef4444", "icono": "flame"},
    {"hoja": "Movimientos en masa", "nombre": "Movimientos en masa", "slug": "movimientos_en_masa",
     "categoria_geo": "Geodinamica externa", "orden": 9, "color": "#a16207",
     "icono": "mountain"},
]

PELIGRO_POR_HOJA = {p["hoja"]: p for p in PELIGROS}
PELIGRO_POR_NOMBRE = {p["nombre"]: p for p in PELIGROS}
SLUGS_PELIGRO = [p["slug"] for p in PELIGROS]

# Las dos grafías con las que la misma fuente aparece en los Excel.
FUENTES = [
    {"nombre": "SIGRID_CENEPRED", "sigla": "SIGRID_CENEPRED"},
    {"nombre": "SINAGERD_CENEPRED", "sigla": "SINAGERD_CENEPRED"},
]
# El Excel de frecuencia invierte el orden en 8 filas; se normaliza al escribir.
ALIAS_FUENTE = {"CENEPRED_SIGRID": "SIGRID_CENEPRED"}

# Categorías y tipos de evento del Excel de frecuencia, con el encabezado exacto de cada
# columna. `columna_total` es el subtotal TOT_* que se guarda como total declarado (ADR-D1).
CATEGORIAS_EVENTO: list[dict] = [
    {
        "nombre": "Geodinámica externa",
        "slug": "geodinamica_externa",
        "orden": 1,
        "columna_total": "TOT_GEODINAMICA EXTERNA",
        "eventos": [
            ("Huayco", "huayco", "HUAYCO"),
            ("Deslizamiento", "deslizamiento", "DESLIZAMIENTO"),
            ("Aluvión", "aluvion", "ALUVIÓN"),
            ("Derrumbe", "derrumbe", "DERRUMBE"),
            ("Reptación", "reptacion", "REPTACIÓN"),
            ("Flujo de detritos", "flujo_de_detritos", "FLUJO DE DETRITOS"),
        ],
    },
    {
        "nombre": "Geodinámica interna",
        "slug": "geodinamica_interna",
        "orden": 2,
        "columna_total": "TOT_GEODINAMICA INTERNA",
        "eventos": [("Sismo", "sismo_evento", "SISMO")],
    },
    {
        "nombre": "Meteorológicos / oceanográficos",
        "slug": "meteorologico",
        "orden": 3,
        "columna_total": "TOT_METEREOLÓGICOS / OCEANOGRÁFICOS",
        "eventos": [
            ("Helada", "helada", "HELADA"),
            ("Baja temperatura", "baja_temperatura", "BAJA TEMPERATURA"),
            ("Vientos fuertes", "vientos_fuertes", "VIENTOS FUERTES"),
            ("Friaje", "friaje_evento", "FRIAJE"),
            ("Granizadas", "granizadas", "GRANIZADAS"),
            ("Inundación", "inundacion_evento", "INUNDACIÓN"),
            ("Lluvias intensas", "lluvias_intensas_evento", "LLUVIAS INTENSAS"),
            ("Nevada", "nevada", "NEVADA"),
            ("Sequía", "sequia_evento", "SEQUÍA"),
            ("Déficit hídrico", "deficit_hidrico", "DÉFICIT HÍDRICO"),
            ("Tormenta eléctrica", "tormenta_electrica", "TORMENTA ELECTRICA"),
        ],
    },
    {
        # Ojo: aquí "Incendio forestal" es inducido por acción humana, mientras que en el
        # Excel de niveles el mismo fenómeno lleva TIP_PELIG = Metereologicas. Cada eje
        # conserva la taxonomía de su fuente; la UI no las mezcla.
        "nombre": "Inducidos por la acción humana",
        "slug": "inducido_humano",
        "orden": 4,
        "columna_total": "TOT_INDUCIDOS POR LA ACCIÓN HUMANA",
        "eventos": [
            ("Colapso por antigüedad", "colapso_por_antiguedad", "COLAPSO POR ANTIGÜEDAD"),
            ("Incendio forestal", "incendio_forestal", "INCENDIO FORESTAL"),
            ("Incendio", "incendio", "INCENDIO"),
        ],
    },
]

# Los slugs de evento llevan sufijo `_evento` cuando colisionan con un slug de peligro
# (sismo, friaje, inundación, sequía, lluvias intensas): son ejes distintos —exposición vs.
# emergencias registradas— y un slug compartido los haría indistinguibles en la URL y en Meili.

NIVELES = {1: "Bajo", 2: "Medio", 3: "Alto", 4: "Muy alto"}
