"""Contrato del API de territorio y peligros (spec 02).

Se prueba **la forma del payload y el significado de cada cifra**, no la implementación. Un
refactor puede reescribir las consultas por dentro; lo que no puede es cambiar qué unidad
representa un número, porque hay gráficos y textos publicados que dependen de eso.
"""
import pytest

pytestmark = pytest.mark.django_db


def test_provincias_y_distritos_van_sin_paginar(api, datos_muestra):
    """Alimentan dos `<select>`: paginarlos obligaría al cliente a recorrer páginas para un combo."""
    provincias = api.get("/api/territorio/provincias/").json()
    distritos = api.get("/api/territorio/distritos/").json()

    assert isinstance(provincias, list) and isinstance(distritos, list)
    assert set(provincias[0]) >= {"ubigeo", "nombre"}
    assert set(distritos[0]) >= {"ubigeo", "nombre", "provincia", "ubigeo_provincia"}


def test_distritos_se_filtran_por_ubigeo_o_por_nombre(api, datos_muestra):
    """El frontend manda ubigeo cuando lo tiene y nombre cuando viene del selector del mapa."""
    por_ubigeo = api.get("/api/territorio/distritos/?provincia=0801").json()
    por_nombre = api.get("/api/territorio/distritos/?provincia=CUSCO").json()

    assert len(por_ubigeo) > 0
    assert [d["ubigeo"] for d in por_ubigeo] == [d["ubigeo"] for d in por_nombre]


def test_forma_del_detalle_de_un_centro_poblado(api, datos_muestra):
    datos = api.get("/api/ccpp/0801010001/").json()

    assert set(datos) >= {
        "codigo", "nombre", "categoria", "departamento", "provincia", "distrito",
        "ubigeo_distrito", "lat", "lon", "altitud", "poblacion", "clasificaciones",
    }
    assert datos["departamento"] == "CUSCO"
    assert datos["ubigeo_distrito"] == "080101"
    clasificacion = datos["clasificaciones"][0]
    assert set(clasificacion) >= {"peligro", "peligro_slug", "nivel", "fuente", "fuente_url"}
    assert clasificacion["nivel"] in {1, 2, 3, 4}


def test_un_centro_poblado_sin_clasificar_trae_lista_vacia_no_nivel_bajo(api, datos_muestra):
    """«Sin dato» y «nivel 1» son cosas distintas y el API no las mezcla.

    Si el detalle inventara un nivel para los no evaluados, los 5,730 centros poblados sin
    información pasarían a contarse como de riesgo bajo.
    """
    from apps.territorio.models import CentroPoblado

    sin_datos = CentroPoblado.objects.filter(clasificaciones__isnull=True).first()
    assert sin_datos, "la muestra no dejó ningún centro poblado sin clasificar"

    datos = api.get(f"/api/ccpp/{sin_datos.codigo}/").json()

    assert datos["clasificaciones"] == []
    assert datos.get("nivel") is None


def test_resumen_declara_sus_dos_unidades(api, datos_muestra):
    """Las dos distribuciones del resumen cuentan cosas distintas, y el payload lo dice.

    `por_ccpp` cuenta centros poblados una vez, en su nivel máximo; `por_peligro` cuenta
    clasificaciones. En los datos reales son 3,238 frente a 10,978 — un factor de 3.4. El bloque
    `unidades` existe para que ningún cliente pueda dibujar una de las dos sin rotularla.
    """
    datos = api.get("/api/peligros/resumen/").json()

    assert set(datos) >= {"total_ccpp", "poblacion_total", "por_ccpp", "por_peligro", "unidades"}
    assert set(datos["por_ccpp"]) == {"niveles", "sin_clasificar"}
    assert set(datos["por_ccpp"]["niveles"]) == {"1", "2", "3", "4"}
    assert set(datos["unidades"]) == {"por_ccpp", "por_peligro"}
    for entrada in datos["por_peligro"]:
        assert set(entrada) == {"peligro", "slug", "niveles", "sin_dato"}


def test_las_dos_unidades_del_resumen_cuadran_con_la_base(api, datos_muestra):
    """Cada bloque tiene que cuadrar con la consulta que le corresponde, no con la otra.

    Es la prueba que habría cazado el error de contar clasificaciones donde se listaban centros
    poblados: en Acomayo daba 225 donde hay 75.
    """
    from apps.peligros.models import ClasificacionPeligro
    from apps.territorio.models import CentroPoblado

    datos = api.get("/api/peligros/resumen/").json()
    ccpp_clasificados = CentroPoblado.objects.filter(clasificaciones__isnull=False).distinct()

    assert datos["total_ccpp"] == CentroPoblado.objects.count()
    assert sum(datos["por_ccpp"]["niveles"].values()) == ccpp_clasificados.count()
    assert datos["por_ccpp"]["sin_clasificar"] == (
        CentroPoblado.objects.count() - ccpp_clasificados.count()
    )
    total_clasificaciones = sum(
        sum(p["niveles"].values()) for p in datos["por_peligro"]
    )
    assert total_clasificaciones == ClasificacionPeligro.objects.count()


def test_el_resumen_se_acota_al_ambito_pedido(api, datos_muestra):
    completo = api.get("/api/peligros/resumen/").json()
    cusco = api.get("/api/peligros/resumen/?provincia=0801").json()

    assert cusco["total_ccpp"] < completo["total_ccpp"]
    assert cusco["total_ccpp"] > 0


# --- Filtros del visor y de la tabla ---------------------------------------


def test_el_listado_ordena_por_nivel_con_los_sin_dato_al_final(api, datos_muestra):
    """Ordenar por gravedad es lo que hace útil la tabla, y `null` no es el nivel más bajo."""
    resultados = api.get("/api/ccpp/?page_size=200").json()["results"]
    niveles = [r["nivel"] for r in resultados]
    con_dato = [n for n in niveles if n is not None]

    assert con_dato == sorted(con_dato, reverse=True)
    assert niveles.index(None) > len(con_dato) - 1 if None in niveles else True


def test_peligro_y_nivel_min_anotan_pero_no_recortan(api, datos_muestra):
    """Sin `clasificados=1` la respuesta trae **todos** los centros poblados.

    Es deliberado —el mapa pinta en gris los que no cumplen— pero significa que `count` no
    responde «cuántos cumplen». La prueba fija las dos semánticas a la vez para que nadie
    «arregle» una rompiendo la otra.
    """
    from apps.territorio.models import CentroPoblado

    total = CentroPoblado.objects.count()
    sin_recortar = api.get("/api/ccpp/?peligro=sismo&nivel_min=4").json()
    recortado = api.get("/api/ccpp/?clasificados=1&peligro=sismo&nivel_min=4").json()

    assert sin_recortar["count"] == total
    assert 0 < recortado["count"] < total
    assert all(r["nivel"] == 4 for r in recortado["results"])


def test_peligro_y_nivel_se_aplican_como_una_sola_condicion(api, datos_muestra):
    """Un centro poblado con sismo en nivel bajo y otro peligro en nivel 4 **no** cumple.

    Aplicar los dos filtros por separado daría un conjunto mayor y falso: cada filtro
    encontraría su propia fila del join y el resultado mentiría.
    """
    from apps.peligros.models import ClasificacionPeligro

    esperados = {
        c.centro_poblado.codigo
        for c in ClasificacionPeligro.objects.filter(
            tipo_peligro__slug="sismo", nivel__gte=3
        ).select_related("centro_poblado")
    }
    respuesta = api.get(
        "/api/ccpp/?clasificados=1&peligro=sismo&nivel_min=3&page_size=200"
    ).json()

    assert {r["codigo"] for r in respuesta["results"]} == esperados


def test_geojson_devuelve_una_feature_por_centro_poblado_con_coordenadas(api, datos_muestra):
    from apps.territorio.models import CentroPoblado

    datos = api.get("/api/ccpp/geojson/").json()
    con_coordenadas = CentroPoblado.objects.exclude(lat=None).exclude(lon=None).count()

    assert datos["type"] == "FeatureCollection"
    assert len(datos["features"]) == con_coordenadas
    primera = datos["features"][0]
    assert primera["geometry"]["type"] == "Point"
    assert len(primera["geometry"]["coordinates"]) == 2
    assert "codigo" in primera["properties"]


def test_cada_punto_declara_cuantas_clasificaciones_aporta(api, datos_muestra):
    """`clasificaciones` es el número que el visor pinta dentro del círculo agrupado.

    Cuenta **filas de clasificación**, no centros poblados: un centro poblado con tres peligros
    evaluados aporta 3. Es la otra unidad del resumen, y por eso el conteo del mapa no puede
    compararse con el de la tabla sin decirlo.
    """
    from apps.peligros.models import ClasificacionPeligro

    datos = api.get("/api/ccpp/geojson/").json()
    por_codigo = {f["properties"]["codigo"]: f["properties"] for f in datos["features"]}

    for clasificacion in ClasificacionPeligro.objects.select_related("centro_poblado")[:50]:
        codigo = clasificacion.centro_poblado.codigo
        if codigo not in por_codigo:  # sin coordenadas: no llega al mapa
            continue
        assert por_codigo[codigo]["clasificaciones"] == ClasificacionPeligro.objects.filter(
            centro_poblado=clasificacion.centro_poblado
        ).count()


def test_los_que_no_pasan_el_filtro_siguen_en_el_mapa_con_cero(api, datos_muestra):
    """El filtro recorta el conteo, no el padrón.

    Los centros poblados que no cumplen se quedan en el `FeatureCollection` para pintarse en
    gris —ausencia de dato no es ausencia de riesgo—, pero aportan 0 al número del grupo. Si
    desaparecieran, el mapa diría que ahí no hay nada que evaluar.
    """
    from apps.peligros.models import ClasificacionPeligro

    sin_filtro = api.get("/api/ccpp/geojson/").json()
    filtrado = api.get("/api/ccpp/geojson/?peligro=sismo&nivel_min=4").json()

    assert len(filtrado["features"]) == len(sin_filtro["features"])

    por_codigo = {f["properties"]["codigo"]: f["properties"] for f in filtrado["features"]}
    cumplen = {
        c.centro_poblado.codigo
        for c in ClasificacionPeligro.objects.filter(
            tipo_peligro__slug="sismo", nivel__gte=4
        ).select_related("centro_poblado")
    }
    assert cumplen, "la muestra no tiene ningún sismo en nivel 4"
    assert all(por_codigo[c]["clasificaciones"] == 1 for c in cumplen if c in por_codigo)
    assert any(p["clasificaciones"] == 0 for p in por_codigo.values())


def test_el_conteo_del_mapa_cuadra_con_el_del_resumen(api, datos_muestra):
    """Sumar los círculos del visor tiene que dar el total que anuncia la pantalla.

    Las dos cifras salen de consultas distintas —una recorre features, la otra agrega en la
    base— y la pantalla las muestra juntas, así que solo una prueba las mantiene alineadas. La
    resta de los sin coordenadas es la única diferencia legítima: el geojson los excluye
    (no se pueden dibujar) y el resumen no.
    """
    from django.db.models import Q

    from apps.peligros.models import ClasificacionPeligro

    geojson = api.get("/api/ccpp/geojson/?peligro=sismo&nivel_min=2").json()
    resumen = api.get("/api/peligros/resumen/?peligro=sismo&nivel_min=2").json()

    del_mapa = sum(f["properties"]["clasificaciones"] for f in geojson["features"])
    del_resumen = sum(sum(p["niveles"].values()) for p in resumen["por_peligro"])
    sin_coordenadas = (
        ClasificacionPeligro.objects.filter(tipo_peligro__slug="sismo", nivel__gte=2)
        .filter(Q(centro_poblado__lat=None) | Q(centro_poblado__lon=None))
        .count()
    )

    assert del_mapa > 0
    assert del_mapa == del_resumen - sin_coordenadas


# --- Frecuencia de emergencias ---------------------------------------------


def test_frecuencia_detalle_forma_y_periodo_por_distrito(api, datos_muestra):
    datos = api.get("/api/peligros/frecuencia/080101/").json()

    assert set(datos) >= {
        "distrito", "ubigeo", "provincia", "rango_fecha", "fuente", "fuente_url",
        "desglose_disponible", "categorias", "total",
    }
    # El periodo es por distrito (23 variantes en la fuente): sin él, dos totales no son
    # comparables y ningún agregado puede anunciar un rango único.
    assert datos["rango_fecha"] == "2003-2022"


def test_adr_d1_cusco_declara_totales_sin_desglose(api, datos_muestra):
    datos = api.get("/api/peligros/frecuencia/080101/").json()

    assert datos["desglose_disponible"] is False
    assert datos["total"] == 134
    assert all(c["solo_total"] is True and c["eventos"] == [] for c in datos["categorias"])


def test_un_distrito_con_desglose_lo_trae_desagregado(api, datos_muestra):
    from apps.territorio.models import Distrito

    ollanta = Distrito.objects.get(nombre__iexact="OLLANTAYTAMBO")
    datos = api.get(f"/api/peligros/frecuencia/{ollanta.ubigeo}/").json()

    assert datos["desglose_disponible"] is True
    assert any(c["eventos"] for c in datos["categorias"])
    assert all(c["solo_total"] is False for c in datos["categorias"])
    assert datos["total"] == sum(c["total"] for c in datos["categorias"])


def test_distrito_sin_dato_responde_404_no_cero(api, datos_muestra):
    """404 y `total: 0` son dos estados vacíos distintos, y la interfaz los dice distinto.

    404 = no sabemos nada de ese distrito (no tiene fila, o la tiene vacía: 22 distritos en los
    datos reales). `total: 0` = hay fila y declara cero emergencias. Colapsarlos publicaría
    «0 emergencias» sobre distritos de los que no hay información.
    """
    from apps.territorio.models import Distrito

    acopia = Distrito.objects.get(nombre__iexact="ACOPIA")

    assert api.get(f"/api/peligros/frecuencia/{acopia.ubigeo}/").status_code == 404


def test_frecuencia_de_un_ubigeo_inexistente_es_404(api, datos_muestra):
    assert api.get("/api/peligros/frecuencia/089999/").status_code == 404


def test_el_listado_trae_los_distritos_de_las_dos_tablas(api, datos_muestra):
    """Incluidos los que solo declaran subtotales (ADR-D1). Sin esto, Cusco no salía en la tabla.

    El detalle de Cusco respondía correctamente mientras el listado lo omitía: el sitio se
    contradecía consigo mismo y ninguna consulta fallaba.
    """
    from apps.peligros.models import FrecuenciaEmergencia, TotalDeclaradoEmergencias

    datos = api.get("/api/peligros/frecuencia/").json()
    con_datos = set(
        FrecuenciaEmergencia.objects.values_list("distrito_id", flat=True)
    ) | set(TotalDeclaradoEmergencias.objects.values_list("distrito_id", flat=True))

    assert isinstance(datos, list)
    assert len(datos) == len(con_datos)
    assert "080101" in {d["ubigeo"] for d in datos}
    assert any(d["desglose_disponible"] is False for d in datos)


def test_el_listado_de_frecuencia_omite_los_distritos_sin_dato(api, datos_muestra):
    """Un distrito sin dato no es una fila de ceros: no aparece."""
    from apps.territorio.models import Distrito

    acopia = Distrito.objects.get(nombre__iexact="ACOPIA")
    datos = api.get("/api/peligros/frecuencia/").json()

    assert acopia.ubigeo not in {d["ubigeo"] for d in datos}


def test_el_listado_de_frecuencia_respeta_el_filtro_de_distrito(api, datos_muestra):
    datos = api.get("/api/peligros/frecuencia/?distrito=CUSCO").json()

    assert [d["ubigeo"] for d in datos] == ["080101"]


def test_el_export_de_frecuencia_respeta_el_filtro_tambien_para_los_declarados(
    api, datos_muestra, sin_throttling
):
    """Un Excel filtrado por un distrito **no** puede acabar con los declarados de toda la región.

    Es lo que pasaba: los declarados se excluían por los ubigeos que devolvía el desglose, y con
    un filtro que no casaba con ningún desglose esa lista salía vacía, así que el `exclude` no
    recortaba nada. El Excel de Ollantaytambo traía a Cusco dentro.
    """
    import io

    import openpyxl

    from apps.territorio.models import Distrito

    ollanta = Distrito.objects.get(nombre__iexact="OLLANTAYTAMBO")
    respuesta = api.get(f"/api/peligros/frecuencia/export.xlsx?distrito={ollanta.ubigeo}")
    libro = openpyxl.load_workbook(io.BytesIO(respuesta.content))
    ubigeos = {
        str(fila[2]) for fila in libro.active.iter_rows(min_row=2, values_only=True) if fila[2]
    }

    assert ubigeos == {ollanta.ubigeo}


def test_tipos_de_peligro_traen_slug_color_y_categoria(api):
    """El frontend pinta el semáforo con estos datos; el slug es la clave de los tiles."""
    tipos = api.get("/api/peligros/tipos/").json()
    filas = tipos["results"] if isinstance(tipos, dict) else tipos

    assert len(filas) == 9
    for tipo in filas:
        assert set(tipo) >= {"nombre", "slug", "color", "categoria_geo"}
        assert "-" not in tipo["slug"]
