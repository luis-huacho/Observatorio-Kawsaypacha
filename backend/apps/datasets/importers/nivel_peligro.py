"""Importa Base_Nivel Peligro_CCPP_Cusco.xlsx (9 hojas, una por peligro).

Porta la lógica de prototype/scripts/xlsx_to_json.py a la BD:
- Deduplica centros poblados por código INEI (aparecen en las 9 hojas).
- Deriva Provincia (ubigeo[:4]) y Distrito (ubigeo[:6]) del código CCPP.
- Solo crea ClasificacionPeligro cuando la fila trae NIVEL_PELI.
- Reemplazo atómico: dentro de una transacción borra las clasificaciones
  activas y las sustituye por las del archivo.
"""
from django.db import transaction

import openpyxl

COLUMNAS_ESPERADAS = [
    "DEPARTAMEN", "PROVINCIA", "DISTRITO", "CODIGO", "NOMB_CPOB", "CATEGORIA",
    "ALTITUD", "LONGITUD", "LATITUD", "POBLACION", "PELIGRO", "TIP_PELIG",
    "NIVEL_PELI", "Fuente", "Link",
]


def importar(upload) -> dict:
    from apps.peligros.models import ClasificacionPeligro, Fuente, TipoPeligro
    from apps.territorio.models import CentroPoblado, Distrito, Provincia

    wb = openpyxl.load_workbook(upload.archivo.path, read_only=True, data_only=True)
    advertencias: list[str] = []
    filas_leidas = 0

    # --- Validación de estructura -----------------------------------------
    for nombre_hoja in wb.sheetnames:
        header = next(wb[nombre_hoja].iter_rows(max_row=1, values_only=True), None)
        if not header or [str(c or "").strip() for c in header[:15]] != COLUMNAS_ESPERADAS:
            raise ValueError(
                f"Hoja '{nombre_hoja}': columnas inesperadas. "
                f"Se esperaba: {', '.join(COLUMNAS_ESPERADAS)}"
            )

    # --- Lectura -----------------------------------------------------------
    ccpp_por_codigo: dict[str, dict] = {}
    clasificaciones: list[dict] = []

    for nombre_hoja in wb.sheetnames:
        for r in wb[nombre_hoja].iter_rows(min_row=2, values_only=True):
            if not r or not r[3]:
                continue
            filas_leidas += 1
            (
                _depto, prov, dist, codigo, nombre, categoria,
                altitud, lon, lat, poblacion,
                peligro, tip_pelig, nivel_peli, fuente, link,
            ) = r[:15]

            codigo = str(codigo).strip()
            if len(codigo) != 10:
                advertencias.append(f"{nombre_hoja}: código CCPP inválido '{codigo}' (omitido)")
                continue

            if codigo not in ccpp_por_codigo:
                ccpp_por_codigo[codigo] = {
                    "codigo": codigo,
                    "nombre": (nombre or "").strip(),
                    "categoria": (categoria or "").strip(),
                    "provincia": (prov or "").strip(),
                    "distrito": (dist or "").strip(),
                    "lat": float(lat) if lat is not None else None,
                    "lon": float(lon) if lon is not None else None,
                    "altitud": int(altitud) if altitud is not None else None,
                    "poblacion": int(poblacion) if poblacion is not None else None,
                }

            if nivel_peli is not None and peligro:
                nivel = int(nivel_peli)
                if not 1 <= nivel <= 4:
                    advertencias.append(
                        f"{nombre_hoja}: nivel fuera de rango ({nivel}) en CCPP {codigo} (omitido)"
                    )
                    continue
                clasificaciones.append({
                    "codigo_ccpp": codigo,
                    "peligro": str(peligro).strip(),
                    "subtipo": (str(tip_pelig).strip() if tip_pelig else ""),
                    "nivel": nivel,
                    "fuente": (str(fuente).strip() if fuente else ""),
                    "fuente_url": (str(link).strip() if link else ""),
                })
    wb.close()

    # --- Escritura atómica --------------------------------------------------
    with transaction.atomic():
        for codigo, datos in ccpp_por_codigo.items():
            provincia, _ = Provincia.objects.get_or_create(
                ubigeo=codigo[:4], defaults={"nombre": datos["provincia"]}
            )
            Distrito.objects.get_or_create(
                ubigeo=codigo[:6],
                defaults={"provincia": provincia, "nombre": datos["distrito"]},
            )

        existentes = set(CentroPoblado.objects.values_list("codigo", flat=True))
        nuevos, actualizar = [], []
        campos = ["nombre", "categoria", "lat", "lon", "altitud", "poblacion"]
        for codigo, d in ccpp_por_codigo.items():
            obj = CentroPoblado(
                codigo=codigo,
                distrito_id=codigo[:6],
                nombre=d["nombre"],
                categoria=d["categoria"],
                lat=d["lat"],
                lon=d["lon"],
                altitud=d["altitud"],
                poblacion=d["poblacion"],
            )
            (actualizar if codigo in existentes else nuevos).append(obj)
        CentroPoblado.objects.bulk_create(nuevos, batch_size=1000)
        if actualizar:
            pk_por_codigo = dict(CentroPoblado.objects.values_list("codigo", "pk"))
            for obj in actualizar:
                obj.pk = pk_por_codigo[obj.codigo]
            CentroPoblado.objects.bulk_update(actualizar, campos, batch_size=1000)

        tipos = {t.nombre: t for t in TipoPeligro.objects.all()}
        fuentes: dict[str, Fuente] = {}
        objetos = []
        pk_ccpp = dict(CentroPoblado.objects.values_list("codigo", "pk"))
        for c in clasificaciones:
            tipo = tipos.get(c["peligro"])
            if tipo is None:
                from django.utils.text import slugify

                tipo = TipoPeligro.objects.create(
                    nombre=c["peligro"], slug=slugify(c["peligro"]), orden=len(tipos)
                )
                tipos[tipo.nombre] = tipo
            fuente = None
            if c["fuente"]:
                fuente = fuentes.get(c["fuente"])
                if fuente is None:
                    fuente, _ = Fuente.objects.get_or_create(nombre=c["fuente"])
                    fuentes[c["fuente"]] = fuente
            objetos.append(
                ClasificacionPeligro(
                    centro_poblado_id=pk_ccpp[c["codigo_ccpp"]],
                    tipo_peligro=tipo,
                    subtipo=c["subtipo"],
                    nivel=c["nivel"],
                    fuente=fuente,
                    fuente_url=c["fuente_url"],
                )
            )
        # Reemplazo: fuera van las clasificaciones anteriores, entran las nuevas.
        ClasificacionPeligro.objects.all().delete()
        ClasificacionPeligro.objects.bulk_create(objetos, batch_size=1000)

    return {
        "filas_leidas": filas_leidas,
        "filas_importadas": len(objetos),
        "centros_poblados": len(ccpp_por_codigo),
        "clasificaciones": len(objetos),
        "advertencias": advertencias[:200],
    }
