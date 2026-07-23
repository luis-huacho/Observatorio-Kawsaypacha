"""Importa Base_Frecuencia_Peligro_Cusco.xlsx (hoja NºEMERGENCIAS).

Formato ancho (distrito × ~25 tipos de evento con subtotales por categoría)
→ formato largo FrecuenciaEmergencia. Los subtotales (TOT_*) y TOTAL no se
almacenan: se calculan agregando.

El Excel no trae ubigeo: el distrito se resuelve por (provincia, nombre)
normalizados contra el catálogo territorial; los no resueltos se reportan
en el log sin abortar la importación.
"""
from django.db import transaction
from django.utils.text import slugify

import openpyxl

# Columnas de evento → categoría SIGRID (en el orden del Excel).
GRUPOS: dict[str, list[str]] = {
    "Geodinámica externa": [
        "HUAYCO", "DESLIZAMIENTO", "ALUVIÓN", "DERRUMBE", "REPTACIÓN", "FLUJO DE DETRITOS",
    ],
    "Geodinámica interna": ["SISMO"],
    "Meteorológicos / oceanográficos": [
        "HELADA", "BAJA TEMPERATURA", "VIENTOS FUERTES", "FRIAJE", "GRANIZADAS",
        "INUNDACIÓN", "LLUVIAS INTENSAS", "NEVADA", "SEQUÍA", "DÉFICIT HÍDRICO",
        "TORMENTA ELECTRICA",
    ],
    "Inducidos por la acción humana": [
        "COLAPSO POR ANTIGÜEDAD", "INCENDIO FORESTAL", "INCENDIO",
    ],
}
HOJA = "NºEMERGENCIAS"


def importar(upload) -> dict:
    from apps.peligros.models import CategoriaEvento, FrecuenciaEmergencia, TipoEvento
    from apps.territorio.models import Distrito
    from apps.territorio.utils import normalizar_nombre

    wb = openpyxl.load_workbook(upload.archivo.path, read_only=True, data_only=True)
    if HOJA not in wb.sheetnames:
        raise ValueError(f"No se encontró la hoja '{HOJA}' en el archivo")
    ws = wb[HOJA]

    filas = ws.iter_rows(values_only=True)
    header = [str(c or "").strip() for c in next(filas)]
    columnas_evento = {  # nombre de columna → índice
        nombre: header.index(nombre)
        for grupo in GRUPOS.values()
        for nombre in grupo
        if nombre in header
    }
    faltantes = [n for g in GRUPOS.values() for n in g if n not in header]
    idx_prov, idx_dist = header.index("PROVINCIA"), header.index("DISTRITO")
    idx_rango = header.index("RANGO FECHA") if "RANGO FECHA" in header else None
    idx_fuente = header.index("FUENTE") if "FUENTE" in header else None
    idx_link = header.index("LINK") if "LINK" in header else None

    advertencias = [f"Columna esperada ausente: {n}" for n in faltantes]
    filas_leidas = 0
    registros: list[dict] = []

    distritos = {
        (d.provincia.nombre and normalizar_nombre(d.provincia.nombre), d.nombre_normalizado): d
        for d in Distrito.objects.select_related("provincia")
    }

    for r in filas:
        if not r or not r[idx_dist]:
            continue
        filas_leidas += 1
        clave = (normalizar_nombre(str(r[idx_prov] or "")), normalizar_nombre(str(r[idx_dist])))
        distrito = distritos.get(clave)
        if distrito is None:
            advertencias.append(
                f"Distrito no resuelto: provincia='{r[idx_prov]}', distrito='{r[idx_dist]}'"
            )
            continue
        for nombre_evento, idx in columnas_evento.items():
            valor = r[idx]
            if valor is None:
                continue
            registros.append({
                "distrito": distrito,
                "evento": nombre_evento,
                "conteo": int(valor),
                "rango_fecha": str(r[idx_rango] or "").strip() if idx_rango is not None else "",
                "fuente": str(r[idx_fuente] or "").strip() if idx_fuente is not None else "",
                "fuente_url": str(r[idx_link] or "").strip() if idx_link is not None else "",
            })
    wb.close()

    with transaction.atomic():
        tipos: dict[str, TipoEvento] = {}
        for orden_cat, (nombre_cat, eventos) in enumerate(GRUPOS.items()):
            categoria, _ = CategoriaEvento.objects.get_or_create(
                slug=slugify(nombre_cat), defaults={"nombre": nombre_cat, "orden": orden_cat}
            )
            for orden_ev, nombre_ev in enumerate(eventos):
                tipo, _ = TipoEvento.objects.get_or_create(
                    slug=slugify(nombre_ev),
                    defaults={
                        "nombre": nombre_ev.capitalize(),
                        "categoria": categoria,
                        "orden": orden_ev,
                    },
                )
                tipos[nombre_ev] = tipo

        FrecuenciaEmergencia.objects.all().delete()
        FrecuenciaEmergencia.objects.bulk_create(
            [
                FrecuenciaEmergencia(
                    distrito=reg["distrito"],
                    tipo_evento=tipos[reg["evento"]],
                    conteo=reg["conteo"],
                    rango_fecha=reg["rango_fecha"],
                    fuente=reg["fuente"],
                    fuente_url=reg["fuente_url"],
                )
                for reg in registros
            ],
            batch_size=1000,
        )

    return {
        "filas_leidas": filas_leidas,
        "filas_importadas": len(registros),
        "advertencias": advertencias[:200],
    }
