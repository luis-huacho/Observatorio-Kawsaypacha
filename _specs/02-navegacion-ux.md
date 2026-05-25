# 02 — Navegación, UX y Diseño Visual

## Mapa del sitio

```
/                            Portada
├── /peligros                Ventana 1 — Mapa de peligros
│   └── /peligros/:cppId     Detalle de un centro poblado
├── /medidas                 Ventana 2 — Qué está funcionando
│   └── /medidas/:slug       Caso individual
├── /inversion               Ventana 3 — Cuánto y cómo se invierte
│   └── /inversion/:ubigeo   Detalle por distrito/provincia
├── /prioridades             Ventana 4 — Dónde invertir primero
├── /normativa               Repositorio normativo
├── /recursos                Directorio de herramientas y links externos
├── /sobre                   Sobre el observatorio (gobernanza, componentes)
└── /buscar?q=...            Resultados de búsqueda global
```

## Header (persistente)

```
[Logo Kawsaypacha]   Peligros  Medidas  Inversión  Prioridades  Normativa  |  🔍 Buscar
```

En mobile: hamburger menu, búsqueda como icono que expande.

## Portada — estructura

1. **Hero** — frase fuerte ("Observatorio del riesgo y la adaptación climática en Cusco") + sub-frase + CTA "Explorar mi distrito" (abre selector geográfico).
2. **4 tarjetas grandes** una por ventana, con icono, pregunta y métrica destacada (ej. "8.969 centros poblados monitoreados").
3. **Buscador prominente** (texto libre + selector provincia/distrito).
4. **Franja de cifras clave** — número de distritos con presupuesto PPR 0068, % de CCPP con peligro alto, etc.
5. **Bloque "Casos recientes"** — 3 cards de la Ventana 2.
6. **Footer** — logos (PREDES, donantes), contacto, fuentes oficiales, enlace a la metodología.

## Ventana 1 — Peligros (detalle)

**Layout:** sidebar izquierdo (filtros) + mapa central + panel inferior colapsable (lista/tabla).

- **Filtros:** provincia → distrito → centro poblado; tipo de peligro (9 opciones); nivel (1-4).
- **Mapa:** Leaflet, capa base CartoDB Voyager, markers o coropleta de distritos según zoom.
  - Cada CCPP se colorea con escala semáforo (verde/amarillo/naranja/rojo) según `NIVEL_PELI`.
  - Click en CCPP → popup con nombre, categoría, población, niveles por peligro, fuente.
  - Click en "Ver detalle" del popup → `/peligros/:cppId`.
- **Calendario estacional** debajo del mapa: matriz peligro × mes con intensidad sombreada (mock en fase 0).
- **Botón "Descargar datos"** (toast "próximamente" en fase 0).

## Ventana 2 — Medidas

Grid de cards filtrables por tipo de peligro. Cada card:
- Thumbnail/video preview
- Tipo de peligro (chip con color semáforo)
- Comunidad/distrito
- Resultado (1 línea)
- Tags: "Sequía", "Comunal", "Forestación", etc.

Filtros laterales: peligro, ámbito (comunal/distrital/regional), resultado (éxito/lección aprendida/mal-adaptación).

## Ventana 3 — Inversión

Tablero con:
- **KPIs superiores:** PIM total PPR 0068 Cusco, % ejecutado, # municipios con presupuesto.
- **Mapa coroplético** por distrito según % asignado a 0068.
- **Barras comparativas** prevención vs. respuesta (gasto agregado).
- **Tabla filtrable** de proyectos/actividades con monto, etapa, ejecutor.
- **Tendencia anual** (línea, últimos 5 años).

## Ventana 4 — Prioridades

- **Mapa multicriterio** distrital con scoring rojo/amarillo/verde.
- **Panel de variables** con sliders (peso ajustable): exposición, población, pobreza, infraestructura crítica, agua, frecuencia.
- **Ranking** lateral de los 20 distritos con mayor prioridad.
- Botón "Ver metodología" → modal con la fórmula.

## Paleta de colores

Partimos de cero, inspirados en montaña andina + semáforo. Configurar en `tailwind.config.ts`.

```
Marca / institucional
  --color-mountain-900: #1F3A2E   (verde profundo, headers)
  --color-mountain-700: #3A6B53
  --color-mountain-500: #6BA585   (acento principal)
  --color-mountain-100: #E6F0EA   (fondos suaves)

Tierra (secundario)
  --color-earth-700:    #7A4A28
  --color-earth-500:    #B8753C
  --color-earth-200:    #F1DCC0

Cielo (info)
  --color-sky-700:      #1F5F8A
  --color-sky-500:      #3E92CC
  --color-sky-200:      #CFE4F2

Semáforo (niveles de peligro/prioridad)
  --color-level-1-low:    #4CAF50   (verde)
  --color-level-2-medium: #FFC107   (amarillo)
  --color-level-3-high:   #FF7043   (naranja)
  --color-level-4-extreme:#D32F2F   (rojo)

Neutros
  --color-ink-900: #1A1A1A
  --color-ink-600: #555
  --color-ink-300: #BDBDBD
  --color-paper:   #FAFAF7   (off-white)
  --color-white:   #FFFFFF

Estado
  --color-mock:    #F97316   (badge "Dato referencial")
```

## Tipografía

- **Display / titulares:** `Plus Jakarta Sans` (Google Fonts, gratuita, moderna pero seria).
- **Cuerpo:** `Inter` (legibilidad excelente en dashboards).
- **Mono / cifras:** `JetBrains Mono` (para códigos de ubigeo, valores numéricos).

Escala (Tailwind):
- `text-xs` 12 — etiquetas
- `text-sm` 14 — secundario
- `text-base` 16 — cuerpo
- `text-lg` 18 — subtítulos
- `text-2xl` 24 — H3
- `text-4xl` 36 — H2
- `text-6xl` 60 — Hero

## Componentes transversales

| Componente | Uso |
| --- | --- |
| `<MockBadge />` | Esquina superior derecha de cualquier card/sección con data mock. Naranja, texto "Dato referencial". |
| `<SourceLink fuente="SIGRID_CENEPRED" url="..."/>` | Pie de toda visualización, con icono ↗. |
| `<SemaforoChip nivel={1\|2\|3\|4} />` | Chip de color para nivel de peligro. |
| `<GeoSelector />` | Cascada provincia → distrito → CCPP, reutilizable. |
| `<DownloadButton format="csv" disabled />` | Botón inhabilitado en fase 0 con tooltip "Próximamente". |
| `<EmptyState />` | Estado vacío con icono + mensaje + sugerencia. |

## Accesibilidad

- Contraste mínimo WCAG AA (4.5:1 para texto normal).
- Navegación completa por teclado.
- `aria-label` en mapas, botones-icono.
- Texto alternativo en todas las imágenes.
- No depender de color solo — los niveles de peligro deben tener también número o ícono.

## Responsive

- **Desktop (≥1024px):** layout pleno, sidebar fijo, mapa grande.
- **Tablet (768-1023):** sidebar colapsable, mapa adaptado.
- **Mobile (<768):** se reconoce que algunas vistas (Ventana 3 tablero) son "desktop primero". En mobile mostrar versión simplificada con énfasis en cifras y selector geográfico.

## Estados de carga y error

- **Skeletons** en cards y tablas (no spinners).
- **Errores de datos** → tarjeta con mensaje claro + botón reintentar (en fase 0 esto solo aplica a fetch de JSON estáticos).

---

**Documentos relacionados:** [[00-vision]], [[01-prototipo-fase0]], [[03-datos-mock]]
