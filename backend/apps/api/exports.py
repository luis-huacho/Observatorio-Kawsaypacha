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
