# 05 — Roadmap por Fases

Fases no atadas a fechas (no hay deadline definido). Cada fase tiene un criterio de salida explícito. **No se inicia la siguiente fase hasta cumplirlo.**

## Fase 0 — Prototipo navegable (AHORA)

**Objetivo:** stakeholders validan estructura, navegación y propuesta visual.

**Entregables:**
- App Vite+React desplegada (estática) en una URL accesible.
- Portada + 4 ventanas + Sobre + Recursos.
- Datos reales de CCPP/peligros cargados desde el Excel.
- Datos mock claramente etiquetados en Medidas, Inversión, Prioridades, Normativa.
- README con cómo correr local y cómo desplegar.

**Criterio de salida:** PREDES aprueba el prototipo (o entrega lista priorizada de cambios) y autoriza fase 1.

**Riesgos:**
- Stakeholders piden funcionalidad que parece simple pero requiere backend → **mantener disciplina:** anotar en backlog, no implementar.
- Confusión real/mock → mitigada por el badge naranja y `*.mock.json`.

## Fase 1 — Backend mínimo viable

**Objetivo:** los datos reales del Excel y al menos un dataset de inversión real viven en Postgres, gestionados desde Django admin.

**Entregables:**
- Django + DRF + Postgres + PostGIS funcionando en VPS.
- Modelo de datos del [[04-arquitectura-fase1]] implementado.
- Comando `importar_ccpp` que carga el Excel a Postgres.
- Carga manual (CSV) de un año de PPR 0068 para Cusco.
- Frontend de fase 0 conectado al API (mismo UX, datos vivos).
- Django admin con permisos para editores PREDES.
- Despliegue con docker-compose, dominio, HTTPS, backups.

**Criterio de salida:** PREDES ha publicado al menos 5 medidas y 5 normas desde el admin, sin tocar código.

## Fase 2 — Ingesta automatizada y enriquecimiento

**Objetivo:** reducir trabajo manual de PREDES y ampliar cobertura.

**Entregables:**
- Scraper Consulta Amigable MEF (Celery beat, nocturno).
- Importadores para SIGRID, SENAMHI (donde haya API; sino plantillas CSV).
- Flujo editorial: borrador → revisión → publicación, con notificaciones email.
- Búsqueda full-text en Postgres.
- Exportación CSV/XLSX funcional en todas las tablas.
- i18n (al menos prepararlo, decidir si se traduce a quechua).

**Criterio de salida:** la inversión PPR 0068 se actualiza sola, sin intervención manual, durante un mes completo.

## Fase 3 — Análisis, productos y co-aprendizaje

**Objetivo:** pasar de "visor" a "herramienta de incidencia".

**Entregables:**
- Generador de "ayudas memoria" descargables (PDF) por distrito.
- Tableros comparativos entre distritos.
- Sección de noticias / artículos de opinión (CMS ligero).
- Repositorio de videos y material de sensibilización con metadatos.
- Talleres y eventos (calendario público).
- Métricas internas: # visitas por ventana, tiempo en página, descargas.

**Criterio de salida:** a definir con PREDES en base al uso real medido.

## Fase 4 — Avanzada

A partir del plan operativo de PREDES (ver [[Editado]]):

- Seguimiento de los 7 procesos de la GRD.
- Monitoreo de implementación del Marco SENDAI (4 prioridades).
- Mapeo de actores locales en GRD/ACC (directorio interactivo).
- Análisis de tendencias y construcción del riesgo (series temporales).
- Posible apertura a reportes ciudadanos (a evaluar).

---

## Principios transversales (en todas las fases)

1. **No construir lo que no se va a usar.** Si una funcionalidad no tiene un usuario nombrado dentro de PREDES o sus aliados, va al backlog.
2. **Toda visualización cita su fuente.** Sin excepciones.
3. **Data mock se elimina, no se acumula.** Cada vez que se cargue data real, se borra el `.mock.json` equivalente en el mismo PR.
4. **De lo general al detalle.** Toda ventana arranca con el agregado regional y permite hacer drill-down.
5. **Localización real.** Cusco, no genérico latinoamericano.

---

**Documentos relacionados:** [[00-vision]], [[01-prototipo-fase0]], [[04-arquitectura-fase1]]
