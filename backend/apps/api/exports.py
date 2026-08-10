"""Exports a Excel (requisito 3 del TDR).

Se usa `write_only=True` de openpyxl: escribe fila a fila sin mantener el libro en memoria, que
es lo que hace viable exportar los 8,968 centros poblados sin que el worker se hinche.
"""
from io import BytesIO

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# Verde de la paleta PREDES, para que el Excel se reconozca como del observatorio.
RELLENO_CABECERA = PatternFill("solid", fgColor="0B3B26")
FUENTE_CABECERA = Font(color="FFFFFF", bold=True)


def libro_excel(hoja: str, cabeceras: list[str], filas, anchos: list[int] | None = None):
    """Devuelve un `HttpResponse` con el .xlsx listo para descargar."""
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(hoja[:31])  # Excel corta los títulos de hoja en 31 caracteres

    if anchos:
        from openpyxl.worksheet.dimensions import ColumnDimension, DimensionHolder

        holder = DimensionHolder(worksheet=ws)
        for i, ancho in enumerate(anchos, start=1):
            holder[get_column_letter(i)] = ColumnDimension(
                ws, index=get_column_letter(i), width=ancho
            )
        ws.column_dimensions = holder

    from openpyxl.cell import WriteOnlyCell

    celdas = []
    for texto in cabeceras:
        celda = WriteOnlyCell(ws, value=texto)
        celda.fill = RELLENO_CABECERA
        celda.font = FUENTE_CABECERA
        celda.alignment = Alignment(vertical="center", wrap_text=True)
        celdas.append(celda)
    ws.append(celdas)

    for fila in filas:
        ws.append(list(fila))

    bufer = BytesIO()
    wb.save(bufer)
    bufer.seek(0)
    return bufer


def respuesta_excel(nombre_archivo: str, hoja: str, cabeceras, filas, anchos=None):
    bufer = libro_excel(hoja, list(cabeceras), filas, anchos)
    respuesta = HttpResponse(
        bufer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    return respuesta


NIVELES = {1: "Bajo", 2: "Medio", 3: "Alto", 4: "Muy alto"}


def filas_ccpp(queryset):
    """Una fila por centro poblado, con su nivel máximo ya anotado.

    Se exporta la misma unidad que muestra la tabla —centros poblados, no clasificaciones—
    para que el Excel cuadre con lo que el usuario tenía en pantalla.
    """
    campos = queryset.select_related("distrito__provincia").iterator(chunk_size=2000)
    for c in campos:
        nivel = getattr(c, "nivel", None)
        yield [
            c.codigo,
            c.nombre,
            c.categoria,
            c.distrito.provincia.nombre,
            c.distrito.nombre,
            c.distrito_id,
            c.poblacion,
            c.altitud,
            c.lat,
            c.lon,
            nivel or "",
            NIVELES.get(nivel, "Sin dato clasificado"),
        ]


CABECERAS_CCPP = [
    "Código INEI", "Centro poblado", "Categoría", "Provincia", "Distrito", "Ubigeo distrito",
    "Población", "Altitud (m)", "Latitud", "Longitud", "Nivel", "Nivel (descripción)",
]
ANCHOS_CCPP = [13, 30, 14, 18, 18, 14, 11, 11, 12, 12, 7, 20]


CABECERAS_INVERSION = [
    "Ejercicio", "Corte", "Fuente", "Código MEF", "Entidad", "Ámbito", "Provincia", "Distrito",
    "Ubigeo distrito", "PIA (0068)", "PIM (0068)", "Devengado (0068)", "% ejecución",
    "Saldo por ejecutar", "Variación PIA-PIM", "PIM institucional", "% del 0068 sobre el total",
    "PIM proyectos", "PIM actividades", "% en proyectos",
]
ANCHOS_INVERSION = [10, 10, 26, 12, 42, 14, 18, 18, 14, 15, 15, 15, 12, 17, 17, 17, 20, 15, 15, 13]


def filas_inversion(filas, ejercicio):
    """Una fila por entidad, con los derivados ya calculados por `inversion.consultas`.

    Se exportan los mismos números que la pantalla —no los recalcula el export— y cada fila
    repite ejercicio, corte y fuente: el archivo viaja suelto por correo, y sin el corte nadie
    puede saber que un 47 % de ejecución es de medio año.
    """
    for f in filas:
        yield [
            ejercicio.anio,
            ejercicio.corte,
            ejercicio.get_fuente_display(),
            f["codigo"],
            f["entidad"],
            f["ambito"],
            f["provincia"] or "",
            f["distrito"] or "",
            f["ubigeo_distrito"] or "",
            f["pia"],
            f["pim"],
            f["devengado"],
            f["pct_ejecucion"],
            f["saldo"],
            f["variacion_pia_pim"],
            f["pim_institucional"],
            f["pct_0068_institucional"],
            f["pim_proyectos"],
            f["pim_actividades"],
            f["pct_proyectos"],
        ]
