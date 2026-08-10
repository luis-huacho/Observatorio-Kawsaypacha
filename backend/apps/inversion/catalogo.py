"""Catálogo canónico de la ventana Inversión: procesos de la GRD y su mapeo.

La hoja «Campos» del Excel del cliente pide el reparto del PP 0068 **según los procesos de la
GRD**, pero ninguna fuente lo trae: hay que derivarlo. Este módulo es esa derivación, y vive
aquí —y no en el importador— porque la siembra y el importador lo necesitan igual, y porque el
mapeo es una interpretación revisable, no una regla del código: `ClasificacionActividad` se
puede editar en el admin y lo que se edita gana.

**El grano es la actividad, no el producto.** A nivel de producto, «3000001 Acciones comunes»
(34.6 % del PIM municipal de 2026) y los proyectos de inversión (40.7 %) dejarían tres cuartas
partes del dinero en dos cajones que no dicen nada. Las 30 actividades del programa sí nombran
el proceso: «Atención de actividades de emergencia» es respuesta y «Mantenimiento de cauces»
es reducción, aunque las dos cuelguen de productos distintos.

**Los proyectos se clasifican por el proyecto, no por su acción de obra.** «Expediente técnico»
o «Supervisión y liquidación de obras» son acciones genéricas: el proceso lo da la obra a la que
pertenecen. Como en Cusco los proyectos del 0068 son casi todos defensas ribereñas, drenaje
pluvial y muros de contención, el importador los crea en *prevención y reducción* y los marca
`automatico`, que es lo que permite a PREDES encontrarlos y corregir los que no lo sean.
"""

#: Los cinco procesos que pide la hoja «Campos», más el transversal.
#:
#: El sexto no está en la lista del cliente y se añade porque, sin él, las tres actividades de
#: «Acciones comunes» —monitoreo del programa, instrumentos estratégicos, asistencia técnica—
#: habría que empujarlas a un proceso que no son. Son el 15 % del PIM municipal: repartirlas por
#: conveniencia falsearía justo la cifra que la ventana existe para mostrar.
PROCESOS_GRD: list[dict] = [
    {"slug": "estimacion", "nombre": "Estimación del riesgo", "orden": 1, "color": "#0ea5e9"},
    {"slug": "prevencion_reduccion", "nombre": "Prevención y reducción", "orden": 2,
     "color": "#009257"},
    {"slug": "preparacion", "nombre": "Preparación", "orden": 3, "color": "#f59e0b"},
    {"slug": "respuesta", "nombre": "Respuesta", "orden": 4, "color": "#ef4444"},
    {"slug": "rehabilitacion", "nombre": "Rehabilitación", "orden": 5, "color": "#a16207"},
    {"slug": "gestion_transversal", "nombre": "Gestión transversal", "orden": 6,
     "color": "#64748b"},
]

#: Proceso con el que el importador crea un proyecto de inversión que aún no está en el
#: catálogo. Ver el encabezado: es un punto de partida marcado como automático, no una verdad.
PROCESO_POR_DEFECTO_PROYECTOS = "prevencion_reduccion"

#: código de actividad del PP 0068 → proceso de la GRD.
#:
#: Cubre las 30 actividades presentes en la serie 2022-2026 de Cusco. «Rehabilitación» no
#: aparece: ninguna actividad del programa cae ahí en estos cinco ejercicios, y que su barra
#: salga en cero es un hallazgo, no un fallo del mapeo.
ACTIVIDAD_A_PROCESO: dict[str, str] = {
    # --- Estimación del riesgo ---------------------------------------------
    "5005571": "estimacion",  # Estudios para establecer el riesgo a nivel territorial
    "5005570": "estimacion",  # Estudios de vulnerabilidad y riesgo en servicios públicos
    "5005572": "estimacion",  # Investigación aplicada para la GRD
    "5005575": "estimacion",  # Monitoreo de peligro por sismo, fallas activas y tsunami
    "5005577": "estimacion",  # Monitoreo de peligros hidrometeorológicos y climáticos
    "5005973": "estimacion",  # Monitoreo de peligros de origen glaciar
    "5006236": "estimacion",  # Monitoreo de peligros a la producción agropecuaria
    # --- Prevención y reducción --------------------------------------------
    "5005564": "prevencion_reduccion",  # Mantenimiento de cauces, drenajes y estructuras
    "5005562": "prevencion_reduccion",  # Control de zonas críticas y fajas marginales
    "5005565": "prevencion_reduccion",  # Tratamiento de cabeceras de cuencas
    "5005865": "prevencion_reduccion",  # Técnicas agropecuarias ante peligros hidrometeorológicos
    "5005568": "prevencion_reduccion",  # Inspección de edificaciones (ITSE)
    "5005566": "prevencion_reduccion",  # Sistemas y tecnologías constructivas para edificaciones
    "5005567": "prevencion_reduccion",  # Planificación urbana incorporando la GRD
    "5005585": "prevencion_reduccion",  # Seguridad físico funcional de servicios públicos
    "5005582": "prevencion_reduccion",  # Medidas de protección ante bajas temperaturas
    # --- Preparación --------------------------------------------------------
    "5005611": "preparacion",  # Administración y almacenamiento de kits
    "5005610": "preparacion",  # Administración y almacenamiento de infraestructura móvil
    "5005612": "preparacion",  # Centros y espacios de monitoreo de emergencias (COE)
    "5005561": "preparacion",  # Brigadas para la atención frente a emergencias
    "5005560": "preparacion",  # Simulacros en gestión reactiva
    "5003293": "preparacion",  # Sistema de alerta temprana y de comunicación
    "5005580": "preparacion",  # Formación y capacitación en GRD y ACC
    "5005581": "preparacion",  # Campañas comunicacionales
    "5005583": "preparacion",  # Organización y entrenamiento de comunidades
    # --- Respuesta ----------------------------------------------------------
    "5006144": "respuesta",  # Atención de actividades de emergencia
    "5006269": "respuesta",  # Prevención, control, diagnóstico y tratamiento de coronavirus
    # --- Gestión transversal ------------------------------------------------
    "5004279": "gestion_transversal",  # Monitoreo, supervisión y evaluación del programa
    "5004280": "gestion_transversal",  # Desarrollo de instrumentos estratégicos para la GRD
    "5005609": "gestion_transversal",  # Asistencia técnica y acompañamiento en GRD
}


def es_proyecto(codigo_producto: str) -> bool:
    """Un código de producto/proyecto que empieza en 2 es un proyecto de inversión.

    Verificado sobre las 19,300 filas del 0068: los que empiezan en 2 son proyectos y los que
    empiezan en 3, actividades. Es la misma regla que usa `scripts/consolidar_pp0068.py`, y
    derivarla del código evita depender de cómo nombra cada fuente esa distinción (el MEF dice
    ACTIVIDAD; el Excel del cliente, «Producto»).
    """
    return codigo_producto.startswith("2")


def codigo_clasificable(codigo_producto: str, codigo_actividad: str) -> str:
    """Devuelve el código cuyo nombre dice de qué proceso es la fila.

    Para una actividad, la propia actividad. Para un proyecto, el proyecto: sus acciones de obra
    («expediente técnico», «gestión y administración») son genéricas y se repiten en obras de
    procesos distintos, así que clasificarlas repartiría el mismo código entre varios procesos.
    """
    return codigo_producto if es_proyecto(codigo_producto) else codigo_actividad
