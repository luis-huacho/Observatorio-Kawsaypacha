# 01 — Fase 0: Prototipo Navegable de Validación

> **Meta única de esta fase:** que PREDES y stakeholders puedan abrir un link, recorrer la portada y las 4 ventanas, y dar feedback antes de invertir en backend.

**No hay PostgreSQL. No hay Django. No hay autenticación. No hay admin.** Solo un front-end estático con datos mock y los datos reales del Excel base convertidos a JSON.

## Entregable

Un sitio web estático desplegable en un VPS (o Vercel/Netlify para validar más rápido) con:

1. **Portada** — propuesta de valor, accesos a las 4 ventanas, búsqueda visible.
2. **Ventana 1 — Peligros** (mapa interactivo, con datos reales del Excel).
3. **Ventana 2 — Medidas** (con datos mock, claramente etiquetados).
4. **Ventana 3 — Inversión** (con datos mock).
5. **Ventana 4 — Prioridades** (con datos mock o cálculo simplificado).
6. **Sobre el observatorio** (estructura, componentes, equipo, contacto).
7. **Recursos** (links a SIGRID, INGEMMET, IGP, ANA, SENAMHI, INAIGEM, MEF).

## Stack técnico (fase 0)

| Capa | Elección | Razón |
| --- | --- | --- |
| Framework | **Vite + React + TypeScript** | Rápido, estándar, sin lock-in. TS para detectar errores en datos mock. |
| Estilos | **TailwindCSS** | Velocidad de prototipado, paleta semántica configurable. |
| Routing | **React Router v6** | Estándar. Rutas declarativas. |
| Mapas | **react-leaflet + Leaflet** | Open source, sin API key, suficiente para coropletas y markers. Tiles desde OpenStreetMap o CartoDB. |
| Gráficos | **Recharts** | API declarativa, buena con TS, tamaño razonable. |
| Iconos | **lucide-react** | Set consistente, tree-shakeable. |
| Datos | **JSON estáticos en `/public/data/`** | Servidos como archivos. Cero backend. |
| i18n | No en fase 0 | Todo en español. Si después se quiere quechua, lo añadimos. |
| Tests | **Vitest** mínimo (smoke tests de rutas) | No invertir en tests profundos hasta validar diseño. |
| Hosting | **VPS con nginx** sirviendo `dist/` estático | También opción Vercel/Netlify para iteraciones rápidas. |

**No usar** todavía: Redux/Zustand (no hay estado complejo), tRPC, GraphQL, Sentry, Storybook, Cypress. Postponer hasta fase 1.

## Estructura del repo (fase 0)

```
/
├── _specs/                    # estos documentos
├── data/                      # fuente original (Excel base)
├── prototype/                 # ← la app de fase 0
│   ├── public/
│   │   └── data/
│   │       ├── ccpp.json      # centros poblados con coords (del Excel)
│   │       ├── peligros.json  # niveles por CCPP × peligro (del Excel)
│   │       ├── medidas.mock.json
│   │       ├── inversion.mock.json
│   │       ├── prioridades.mock.json
│   │       └── normativa.mock.json
│   ├── src/
│   │   ├── routes/            # una carpeta por ventana
│   │   ├── components/        # Layout, Header, MockBadge, MapView, etc.
│   │   ├── lib/               # helpers: loadJson, semaforo, formateo
│   │   ├── styles/
│   │   └── App.tsx
│   ├── scripts/
│   │   └── xlsx-to-json.ts    # convierte Base_Nivel Peligro_CCPP_Cusco.xlsx → JSON
│   ├── index.html
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── package.json
└── brainstorming.md           # ya existente
```

## Datos: qué es real, qué es mock

| Dataset | Origen en fase 0 | Marcar como mock? |
| --- | --- | --- |
| Centros poblados (coords, población, código INEI) | Excel `Base_Nivel Peligro_CCPP_Cusco.xlsx` → script de conversión | **No**, es real |
| Niveles de peligro (9 tipos × CCPP) | Mismo Excel | **No**, es real (pero está disperso — pocos CCPP tienen nivel asignado por tipo) |
| Medidas que funcionan (casos, videos) | Inventado | **Sí**, mock |
| Inversión PPR 0068 | Inventado | **Sí**, mock |
| Multicriterio (Ventana 4) | Cálculo de juguete sobre datos reales + variables inventadas | **Sí**, mock parcial |
| Normativa | Lista mínima inventada | **Sí**, mock |

**Convención visual:** cualquier sección/tabla/tarjeta con datos mock muestra un badge naranja `"Dato referencial"` en la esquina superior. En código, cada archivo mock se llama `*.mock.json` para que sea trivial encontrarlos y reemplazarlos en fase 1.

## Lo que el prototipo NO necesita resolver

- Performance con datasets enormes (8.969 CCPP cabe en JSON, ~2-3 MB, aceptable para validar).
- Búsqueda potente (un input que filtra en cliente es suficiente).
- Exportación CSV real (botón puede mostrar toast "próximamente").
- Roles, permisos, login.
- SEO avanzado (es un prototipo interno de validación).
- Internacionalización.
- PWA / offline.

## Criterio de cierre de fase 0

PREDES revisa el prototipo y entrega feedback en **uno** de estos formatos:

- Sesión grabada de walkthrough con stakeholders, o
- Lista numerada de cambios solicitados, o
- Aprobación explícita para pasar a fase 1.

Solo entonces se inicia [[04-arquitectura-fase1]].
