# 00 — Visión del Observatorio Kawsaypacha

## Qué es

Plataforma web para **monitorear y dar seguimiento a la Gestión del Riesgo de Desastres (GRD) y la Adaptación al Cambio Climático (ACC)** en la región Cusco, Perú. Operado por PREDES.

No es un blog ni un visor cartográfico tradicional: es un híbrido entre **visor de datos**, **biblioteca de conocimiento** y **herramienta de incidencia política**.

## Para quién

| Audiencia | Necesidad principal |
| --- | --- |
| Decisores políticos (gobiernos locales, provinciales, regionales, GORE Cusco, MIDEF, MINAM) | Identificar peligros, priorizar inversión, comparar gasto prevención vs. respuesta |
| Sociedad civil (ONG, universidades, RSE, cooperación internacional) | Acceder a evidencia, casos de éxito, normativa actualizada |
| Medios de comunicación | Datos confiables y exportables para reportería |
| Equipos PREDES (interno) | Sistematizar conocimiento, publicar productos, monitorear evolución |

## Promesa de valor

> **De lo general al detalle**: parto de un mapa regional y termino con la actividad presupuestal de una municipalidad. Todo navegable, filtrable, exportable y con fuentes citadas.

## Objetivos estratégicos

1. **Visibilizar escenarios de riesgo** asociados a peligros climáticos a nivel de centro poblado.
2. **Identificar prácticas exitosas, fracasos y casos de mal-adaptación** en GRD y ACC.
3. **Detectar cuellos de botella** que impiden a los gobiernos subnacionales gestionar el riesgo y adaptarse.

## Las 4 Ventanas (estructura central de la app)

| Ventana | Pregunta del usuario | Producto |
| --- | --- | --- |
| 1 — Peligros | ¿Qué peligros afectan más a mi distrito? | Mapa interactivo de exposición + calendario estacional + PPRD |
| 2 — Medidas | ¿Qué medidas están funcionando? | Casos, videos, material de sensibilización por tipo de peligro |
| 3 — Inversión | ¿Cuánto y cómo se invierte (PPR 0068)? | Tableros de presupuesto regional/provincial/distrital + comparación prevención vs. respuesta |
| 4 — Prioridades | ¿Dónde debería invertirse primero? | Mapa multicriterio (exposición + población + pobreza + infraestructura + agua + frecuencia) |

## Componentes operativos (mapeo a la app)

| Componente del Observatorio | Cómo se expresa en la app |
| --- | --- |
| Gobernanza | Sección "Sobre el observatorio" + página de directorio + flujo de aprobación editorial (fase 1) |
| Comunicación y divulgación | Sección de casos, videos, material descargable, noticias |
| Gestión del conocimiento | Las 4 ventanas + repositorio de normativa + datos exportables |

## Criterios de éxito del producto

- Un funcionario distrital encuentra el nivel de peligro de su centro poblado en **<30 segundos** desde la portada.
- Un periodista descarga un dataset de inversión PPR 0068 en **<3 clics**.
- Cada dato visible cita su fuente (SIGRID, INEI, MEF, SENAMHI, INGEMMET, etc.) con enlace verificable.
- La data referencial/mock está claramente identificada para evitar errores de interpretación.

## Lo que NO es

- No reemplaza al SIGRID ni al CENEPRED — los **consume y contextualiza**.
- No es un sistema de alerta temprana en tiempo real.
- No es una red social ni recoge reportes ciudadanos en su fase MVP.

## Localización

- Español de Perú (vos no, tú).
- Topónimos en quechua respetados (Chahuaytiri, Sacaca, Pampallacta).
- Imágenes y referencias culturales **deben ser de Cusco/Andes peruanos**.

---

**Documentos relacionados:**
- [[01-prototipo-fase0]] — qué construimos primero (prototipo de validación)
- [[02-navegacion-ux]] — estructura de navegación y diseño visual
- [[03-datos-mock]] — cómo manejamos data real vs. mock
- [[04-arquitectura-fase1]] — qué viene después de validar
- [[05-roadmap]] — fases y criterios de salto entre fases
