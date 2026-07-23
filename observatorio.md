# Informe de actividades — Observatorio Kawsaypacha (PREDES)

**Período cubierto:** 25 de mayo de 2026
**Responsable:** Luis Huacho
**Estado del proyecto:** Fase 0 — Prototipo navegable de validación

---

## Resumen

Se completó la fase de descubrimiento del Observatorio Kawsaypacha: revisión de documentación entregada por PREDES, generación de la especificación funcional y técnica del producto, y construcción de un prototipo navegable sin backend para validar con stakeholders antes de invertir en infraestructura.

---

## Detalle de actividades

| # | Actividad | Entregable | Horas |
|---|---|---|---|
| 1 | Revisión de documentación PREDES y materiales base (brainstorming, notas de reunión, Excel `Base_Nivel Peligro_CCPP_Cusco.xlsx` con 9 hojas / 8.969 centros poblados) | `brainstorming.md`, `practice.md`, `Editado.md` | 2.0 |
| 2 | Análisis del dataset base (estructura de columnas, sparsity por peligro, cobertura geográfica regional) | Notas en `_specs/03-datos-mock.md` | 1.0 |
| 3 | Generación de especificación del producto: visión, 4 ventanas (Peligros, Medidas, Inversión PPR 0068, Prioridades), navegación, paleta, datos mock, arquitectura fase 1 y roadmap | `_specs/00-vision.md` → `_specs/05-roadmap.md` + `_specs/README.md` (7 documentos, ~846 líneas) | 3.5 |
| 4 | Decisiones técnicas fijadas: React (Vite+TS), VPS, Django+DRF+PostgreSQL+PostGIS para fase 1, acceso 100% público | Recogido en `_specs/04-arquitectura-fase1.md` | 0.5 |
| 5 | Construcción del prototipo navegable Fase 0 (Vite + React + TS + Tailwind): layout, header/footer, 12 rutas (Home, Peligros, PeligroDetalle, Medidas, MedidaDetalle, Inversión, Prioridades, Buscar, Normativa, Recursos, Sobre, NotFound), 9 componentes (MapaPeligros, GeoSelector, SemaforoChip, MockBadge, SourceLink, EmptyState, etc.) | `prototype/` | 4.0 |
| 6 | Script de conversión XLSX → JSON estático para alimentar el prototipo sin backend | `prototype/scripts/xlsx_to_json.py` | 0.5 |
| 7 | Convención de datos mock (sufijo `*.mock.json`, flag `_mock: true`, badge visible "Dato referencial") | `_specs/03-datos-mock.md`, componente `MockBadge.tsx` | 0.5 |
| 8 | Configuración de build y despliegue (Vite, Tailwind, PostCSS, Vercel) | `vite.config.ts`, `tailwind.config.ts`, `vercel.json` | 0.5 |
| 9 | Ajustes de portada tras feedback inicial (retiro del bloque informativo de prototipo en home) | Commit `92fc823` | 0.5 |

**Total: 13.0 horas**

---

## Commits del período

- `1f72117` — git init
- `6784c4b` — Add Phase 0 prototype: navigable validation app
- `d42c2c5` — prototype
- `92fc823` — Quitar bloque informativo de prototipo en home

---

## Próximos pasos

1. Sesión de validación con PREDES sobre el prototipo navegable.
2. Recoger feedback sobre estructura de las 4 ventanas y portada.
3. Solo tras aprobación: planificar arranque de Fase 1 (Django + PostgreSQL + PostGIS) según `_specs/04-arquitectura-fase1.md` y `_specs/05-roadmap.md`.