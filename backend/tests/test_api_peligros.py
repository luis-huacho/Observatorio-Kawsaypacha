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
        assert set(entrada) == {"peligro", "slug", "niveles", "centros_poblados", "sin_dato"}


def test_el_visor_ya_no_publica_poblacion(api, datos_muestra):
    """La población sale del visor: la fuente la trae, pero no sirve como magnitud.

    948 de los 8,968 centros poblados valen 0 y la mediana es 17 habitantes, así que como
    canal visual —radio del símbolo, columna comparable— es ilegible y engañosa.

    Sale de **la lista y del mapa**, que son las piezas donde se leía como escala. Sigue en la
    ficha individual, donde es un atributo del lugar, y en `poblacion_total` del resumen, que
    es lo que el comparador de distritos publica como población del ámbito.
    """
    listado = api.get("/api/ccpp/?page_size=5").json()
    geojson = api.get("/api/ccpp/geojson/").json()

    assert all("poblacion" not in fila for fila in listado["results"])
    assert all("poblacion" not in f["properties"] for f in geojson["features"])
    assert "poblacion" in api.get("/api/ccpp/0801010001/").json()
    assert "poblacion_total" in api.get("/api/peligros/resumen/").json()


def test_por_peligro_cuenta_centros_poblados_dentro_de_cada_fila(api, datos_muestra):
    """Dentro de un tipo de peligro, «clasificaciones» y «centros poblados» son lo mismo.

    Lo garantiza la constraint `unica_clasificacion_ccpp_peligro`: un centro poblado no puede
    tener dos filas del mismo peligro. Por eso la grilla de resultados puede rotular cada fila
    como centros poblados sin ambigüedad — la unidad solo se vuelve equívoca al **sumar** entre
    tipos, que es donde aparecen las 10,978 frente a las 3,238.
    """
    from apps.peligros.models import ClasificacionPeligro

    datos = api.get("/api/peligros/resumen/").json()

    for entrada in datos["por_peligro"]:
        ccpp_del_tipo = (
            ClasificacionPeligro.objects.filter(tipo_peligro__slug=entrada["slug"])
            .values("centro_poblado")
            .distinct()
            .count()
        )
        assert entrada["centros_poblados"] == ccpp_del_tipo
        assert entrada["centros_poblados"] == sum(entrada["niveles"].values())


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


def test_los_filtros_anotan_pero_no_recortan(api, datos_muestra):
    """Sin `clasificados=1` la respuesta trae **todos** los centros poblados.

    Es deliberado —el mapa pinta en gris los que no cumplen— pero significa que `count` no
    responde «cuántos cumplen». La prueba fija las dos semánticas a la vez para que nadie
    «arregle» una rompiendo la otra.
    """
    from apps.territorio.models import CentroPoblado

    total = CentroPoblado.objects.count()
    sin_recortar = api.get("/api/ccpp/?peligros=sismo&niveles=4").json()
    recortado = api.get("/api/ccpp/?clasificados=1&peligros=sismo&niveles=4").json()

    assert sin_recortar["count"] == total
    assert 0 < recortado["count"] < total
    assert all(r["nivel"] == 4 for r in recortado["results"])


def test_peligro_y_nivel_se_aplican_como_una_sola_condicion(api, datos_muestra):
    """Un centro poblado con sismo en nivel bajo y otro peligro en nivel 4 **no** cumple.

    Aplicar los dos filtros por separado daría un conjunto mayor y falso: cada filtro
    encontraría su propia fila del join y el resultado mentiría. Con selección múltiple la
    trampa es la misma y más fácil de pisar: basta con que el centro poblado tenga *alguno*
    de los peligros marcados y *alguno* de los niveles marcados, en filas distintas.
    """
    from apps.peligros.models import ClasificacionPeligro

    esperados = {
        c.centro_poblado.codigo
        for c in ClasificacionPeligro.objects.filter(
            tipo_peligro__slug="sismo", nivel__in=[3, 4]
        ).select_related("centro_poblado")
    }
    respuesta = api.get(
        "/api/ccpp/?clasificados=1&peligros=sismo&niveles=3,4&page_size=200"
    ).json()

    assert {r["codigo"] for r in respuesta["results"]} == esperados


def test_varios_peligros_marcados_unen_sus_centros_poblados(api, datos_muestra):
    """Marcar dos peligros trae la unión, no la intersección: es una lista de casillas."""
    from apps.peligros.models import ClasificacionPeligro

    esperados = {
        c.centro_poblado.codigo
        for c in ClasificacionPeligro.objects.filter(
            tipo_peligro__slug__in=["sismo", "inundacion"], nivel__in=[4]
        ).select_related("centro_poblado")
    }
    assert esperados, "la muestra no tiene sismo ni inundación en nivel 4"

    respuesta = api.get(
        "/api/ccpp/?clasificados=1&peligros=sismo,inundacion&niveles=4&page_size=500"
    ).json()

    assert {r["codigo"] for r in respuesta["results"]} == esperados


def test_los_niveles_no_tienen_que_ser_contiguos(api, datos_muestra):
    """El filtro dejó de ser un umbral: se puede pedir «Muy alto» y «Bajo» sin lo de en medio.

    Con el `nivel_min` de antes esta consulta era imposible de expresar.
    """
    from apps.peligros.models import ClasificacionPeligro

    esperados = {
        c.centro_poblado.codigo
        for c in ClasificacionPeligro.objects.filter(
            tipo_peligro__slug="sismo", nivel__in=[1, 4]
        ).select_related("centro_poblado")
    }
    assert esperados, "la muestra no tiene sismo en niveles 1 ni 4"

    respuesta = api.get(
        "/api/ccpp/?clasificados=1&peligros=sismo&niveles=1,4&page_size=500"
    ).json()
    devueltos = {r["codigo"] for r in respuesta["results"]}

    assert devueltos == esperados
    intermedios = set(
        ClasificacionPeligro.objects.filter(tipo_peligro__slug="sismo", nivel__in=[2, 3])
        .exclude(centro_poblado__clasificaciones__nivel__in=[1, 4])
        .values_list("centro_poblado__codigo", flat=True)
    )
    assert not (devueltos & intermedios)


def test_un_parametro_vacio_equivale_a_no_mandarlo(api, datos_muestra):
    """`peligros=` vacío no restringe nada: es lo mismo que omitirlo.

    Es contrato del API, no de la pantalla. El visor nunca emite este caso —cuando el usuario
    desmarca todas las casillas muestra su estado vacío sin llegar a pedir—, pero el API tiene
    que responder algo definido, y «vacío = sin restricción» es lo que ya hacía `nivel_min`
    con un valor no numérico.
    """
    from apps.territorio.models import CentroPoblado

    total = CentroPoblado.objects.count()

    assert api.get("/api/ccpp/?peligros=&niveles=").json()["count"] == total
    assert api.get("/api/ccpp/").json()["count"] == total
    con_clasificacion = CentroPoblado.objects.filter(clasificaciones__isnull=False).distinct()
    assert (
        api.get("/api/ccpp/?clasificados=1&peligros=&niveles=").json()["count"]
        == con_clasificacion.count()
    )


def test_los_parametros_antiguos_siguen_funcionando(api, datos_muestra):
    """`peligro` y `nivel_min` sobreviven como alias: hay ayudas memoria compartidas con esas URL.

    `nivel_min=3` se traduce a los niveles 3 y 4, que es lo que significaba el umbral.
    """
    nuevo = api.get("/api/ccpp/?clasificados=1&peligros=sismo&niveles=3,4&page_size=200").json()
    antiguo = api.get("/api/ccpp/?clasificados=1&peligro=sismo&nivel_min=3&page_size=200").json()

    assert antiguo["count"] == nuevo["count"] > 0
    assert {r["codigo"] for r in antiguo["results"]} == {r["codigo"] for r in nuevo["results"]}


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
    filtrado = api.get("/api/ccpp/geojson/?peligros=sismo&niveles=4").json()

    assert len(filtrado["features"]) == len(sin_filtro["features"])

    por_codigo = {f["properties"]["codigo"]: f["properties"] for f in filtrado["features"]}
    cumplen = {
        c.centro_poblado.codigo
        for c in ClasificacionPeligro.objects.filter(
            tipo_peligro__slug="sismo", nivel__in=[4]
        ).select_related("centro_poblado")
    }
    assert cumplen, "la muestra no tiene ningún sismo en nivel 4"
    assert all(por_codigo[c]["clasificaciones"] == 1 for c in cumplen if c in por_codigo)
    assert any(p["clasificaciones"] == 0 for p in por_codigo.values())


def test_la_paginacion_no_repite_ni_se_salta_centros_poblados(api, datos_muestra):
    """Recorrer todas las páginas tiene que devolver cada centro poblado **una vez**.

    El orden era `(nivel, nombre)` y el nombre **no es único**: 770 se repiten en el padrón,
    «PUCARA» 21 veces. Con `LIMIT`/`OFFSET` sobre un orden parcial, PostgreSQL no garantiza
    nada entre consultas, así que una fila podía salir en dos páginas y otra en ninguna. Lo
    visible era la tabla repitiendo filas al pulsar «Ver más»; lo grave, los que se perdían.
    """
    vistos: list[str] = []
    pagina = 1
    while True:
        datos = api.get(f"/api/ccpp/?clasificados=1&page_size=7&page={pagina}").json()
        vistos.extend(r["codigo"] for r in datos["results"])
        if not datos["next"]:
            break
        pagina += 1

    assert len(vistos) == len(set(vistos)), "la paginación repitió centros poblados"
    assert len(vistos) == datos["count"], "la paginación se saltó centros poblados"


def test_el_listado_trae_todos_los_peligros_de_cada_centro_poblado(api, datos_muestra):
    """La tabla lista a QUÉ está expuesto cada lugar, no solo su nivel máximo.

    El nivel máximo es un resumen, y con un promedio de 3.4 peligros por centro poblado
    escondía justo lo que se consulta. El orden es el mismo con el que el mapa elige el ícono
    —nivel descendente, y a igualdad el orden del catálogo—, así que las dos vistas nombran
    primero el mismo peligro.
    """
    from apps.peligros.models import ClasificacionPeligro, TipoPeligro

    orden = {t.slug: t.orden for t in TipoPeligro.objects.all()}
    filas = api.get("/api/ccpp/?clasificados=1&page_size=50").json()["results"]
    assert filas

    revisadas = 0
    for fila in filas:
        suyas = list(
            ClasificacionPeligro.objects.filter(
                centro_poblado__codigo=fila["codigo"]
            ).select_related("tipo_peligro")
        )
        esperado = [
            {"slug": c.tipo_peligro.slug, "nombre": c.tipo_peligro.nombre, "nivel": c.nivel}
            for c in sorted(suyas, key=lambda c: (-c.nivel, orden[c.tipo_peligro.slug]))
        ]
        assert fila["peligros"] == esperado
        assert fila["nivel"] == max(c.nivel for c in suyas)
        revisadas += 1

    assert revisadas > 0
    assert any(len(f["peligros"]) > 1 for f in filas), "la muestra no tiene ninguno con varios"


def test_el_desglose_del_listado_respeta_los_filtros(api, datos_muestra):
    """Filtrar por un peligro no puede dejar asomar los demás de ese centro poblado.

    Es la prueba que evita que el prefetch se escriba sin condición: la fila seguiría
    listando heladas con «sismo» marcado, y la tabla contradiría al mapa y a la grilla, que sí
    recortan.
    """
    filas = api.get("/api/ccpp/?clasificados=1&peligros=sismo&page_size=50").json()["results"]
    assert filas

    for fila in filas:
        assert [p["slug"] for p in fila["peligros"]] == ["sismo"]

    # Y con dos niveles sueltos, ninguna fila puede traer uno intermedio.
    filas = api.get("/api/ccpp/?clasificados=1&niveles=1,4&page_size=50").json()["results"]
    assert filas
    for fila in filas:
        assert all(p["nivel"] in (1, 4) for p in fila["peligros"])


def test_la_ficha_no_repite_el_desglose_del_listado(api, datos_muestra):
    """El detalle trae `clasificaciones` —con fuente y respaldo— y no `peligros`.

    Heredarlo del serializer de lista lo dejaría siempre vacío, porque la ficha usa otro
    prefetch, y un campo que siempre viene vacío se lee como «este lugar no tiene ninguno».
    """
    ficha = api.get("/api/ccpp/0801010001/").json()

    assert "peligros" not in ficha
    assert ficha["clasificaciones"]


def test_el_punto_declara_sus_ranuras_para_la_corona(api, datos_muestra):
    """El visor dibuja **un ícono por peligro**, así que el punto trae uno por ranura.

    Van numeradas (`s0`, `n_0`, `s1`, `n_1`…) y no como lista porque las propiedades de una
    fuente agrupada tienen que ser escalares y `icon-image` no sabe indexar un array. El nivel
    lleva guion bajo para no chocar con `n1`…`n4`, que son el desglose que suman los grupos.
    """
    import json

    datos = api.get("/api/ccpp/geojson/").json()
    con_varios = 0

    for feature in datos["features"]:
        props = feature["properties"]
        desglose = json.loads(props["peligros"])

        for indice, entrada in enumerate(desglose):
            assert props[f"s{indice}"] == entrada["s"]
            assert props[f"n_{indice}"] == entrada["n"]
        # Solo las ocupadas: una ranura de más dibujaría un ícono que nadie clasificó.
        assert f"s{len(desglose)}" not in props
        if desglose:
            assert props["s0"] == props["peligro"], "la ranura 0 y el ícono deben coincidir"
        if len(desglose) > 1:
            con_varios += 1

    assert con_varios > 0, "la muestra no tiene ningún centro poblado con varios peligros"


def test_el_punto_declara_el_peligro_que_pinta_su_icono(api, datos_muestra):
    """El símbolo codifica el **tipo** en la forma, así que el punto tiene que decir cuál.

    Cuando varios peligros pasan el filtro gana el de mayor nivel, y si empatan el primero por
    `orden` del catálogo. Se decide **en el servidor** y no en el cliente: el ícono del mapa y
    el desglose del popup salen del mismo cálculo, y duplicarlo es garantizar que se separen.
    """
    from apps.peligros.models import ClasificacionPeligro, TipoPeligro

    orden = {t.slug: t.orden for t in TipoPeligro.objects.all()}
    datos = api.get("/api/ccpp/geojson/").json()

    revisados = 0
    for feature in datos["features"]:
        props = feature["properties"]
        suyas = list(
            ClasificacionPeligro.objects.filter(
                centro_poblado__codigo=props["codigo"]
            ).select_related("tipo_peligro")
        )
        if not suyas:
            assert props["nivel"] == 0 and props["peligro"] == ""
            continue
        gana = min(suyas, key=lambda c: (-c.nivel, orden[c.tipo_peligro.slug]))
        assert props["peligro"] == gana.tipo_peligro.slug
        assert props["nivel"] == gana.nivel
        revisados += 1

    assert revisados > 0, "la muestra no dejó ningún centro poblado clasificado"


def test_el_punto_desglosa_por_nivel_y_por_tipo_para_los_grupos(api, datos_muestra):
    """`n<k>` y `p_<slug>` son lo que suma `clusterProperties` (requisito de agrupación).

    MapLibre solo sabe acumular escalares que ya vengan en el feature, así que un grupo no
    puede decir «de qué» es a menos que cada punto traiga su desglose. Se emiten **solo las
    claves distintas de cero** para no inflar un payload de 2 MB con ceros.
    """
    from apps.peligros.models import ClasificacionPeligro

    datos = api.get("/api/ccpp/geojson/?peligros=sismo,inundacion").json()

    for feature in datos["features"]:
        props = feature["properties"]
        suyas = ClasificacionPeligro.objects.filter(
            centro_poblado__codigo=props["codigo"],
            tipo_peligro__slug__in=["sismo", "inundacion"],
        ).select_related("tipo_peligro")

        por_nivel = {n: sum(1 for c in suyas if c.nivel == n) for n in (1, 2, 3, 4)}
        for n, cuantas in por_nivel.items():
            assert props.get(f"n{n}", 0) == cuantas
            assert not (cuantas == 0 and f"n{n}" in props), f"n{n} en cero no debe emitirse"
        for slug in ("sismo", "inundacion"):
            presente = any(c.tipo_peligro.slug == slug for c in suyas)
            assert props.get(f"p_{slug}", 0) == int(presente)
            assert not (not presente and f"p_{slug}" in props)

        assert sum(props.get(f"n{n}", 0) for n in (1, 2, 3, 4)) == props["clasificaciones"]


def test_el_desglose_del_popup_trae_el_slug_de_cada_peligro(api, datos_muestra):
    """El popup pinta el ícono de cada peligro, y para eso necesita el slug, no solo el nombre."""
    import json

    datos = api.get("/api/ccpp/geojson/").json()
    con_datos = [f for f in datos["features"] if f["properties"]["clasificaciones"] > 0]
    assert con_datos

    desglose = json.loads(con_datos[0]["properties"]["peligros"])
    assert desglose and set(desglose[0]) == {"s", "p", "n"}
    assert desglose == sorted(desglose, key=lambda d: -d["n"])


def test_el_conteo_del_mapa_cuadra_con_el_del_resumen(api, datos_muestra):
    """Sumar los círculos del visor tiene que dar el total que anuncia la pantalla.

    Las dos cifras salen de consultas distintas —una recorre features, la otra agrega en la
    base— y la pantalla las muestra juntas, así que solo una prueba las mantiene alineadas. La
    resta de los sin coordenadas es la única diferencia legítima: el geojson los excluye
    (no se pueden dibujar) y el resumen no.
    """
    from django.db.models import Q

    from apps.peligros.models import ClasificacionPeligro

    geojson = api.get("/api/ccpp/geojson/?peligros=sismo&niveles=2,3,4").json()
    resumen = api.get("/api/peligros/resumen/?peligros=sismo&niveles=2,3,4").json()

    del_mapa = sum(f["properties"]["clasificaciones"] for f in geojson["features"])
    del_resumen = sum(sum(p["niveles"].values()) for p in resumen["por_peligro"])
    sin_coordenadas = (
        ClasificacionPeligro.objects.filter(tipo_peligro__slug="sismo", nivel__in=[2, 3, 4])
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


def test_el_agregado_provincial_cuadra_con_sus_distritos(api, datos_muestra):
    """El gráfico de /peligros pregunta por provincia; el eje de ocurrencia era por distrito."""
    lista = api.get("/api/peligros/frecuencia/?provincia=0801").json()
    provincial = api.get("/api/peligros/frecuencia/provincia/0801/").json()

    assert provincial["total"] == sum(d["total"] for d in lista)
    # Solo cuentan los que tienen algo: los que declaran cero (ADR-D1) no son «con registro».
    assert provincial["distritos_con_registro"] == sum(1 for d in lista if d["total"] > 0)
    assert provincial["distritos_en_provincia"] >= provincial["distritos_con_registro"]


def test_las_dos_agrupaciones_no_suman_lo_mismo_y_el_payload_lo_explica(api, datos_muestra):
    """`familias` incluye los subtotales declarados y `eventos` no puede incluirlos.

    El distrito de Cusco declara sus emergencias por categoría pero **no por evento** (ADR-D1),
    así que agrupar por tipo de evento da el total real y agrupar por evento da menos. No es un
    descuadre: es lo que la fuente sabe. `total_sin_desglose` existe para que la pantalla lo
    diga en vez de dejar que el total cambie al pulsar una casilla.
    """
    datos = api.get("/api/peligros/frecuencia/provincia/0801/").json()

    assert sum(f["conteo"] for f in datos["familias"]) == datos["total"]
    assert sum(e["conteo"] for e in datos["eventos"]) == datos["total"] - datos["total_sin_desglose"]
    assert datos["total_sin_desglose"] > 0, "la muestra no tiene ningún distrito sin desglose"
    assert [d["distrito"] for d in datos["sin_desglose"]]


def test_los_eventos_del_agregado_van_ordenados_y_sin_ceros(api, datos_muestra):
    """Las barras se pintan en el orden que llegan y solo de lo que ocurrió."""
    datos = api.get("/api/peligros/frecuencia/provincia/0801/").json()

    conteos = [e["conteo"] for e in datos["eventos"]]
    assert conteos == sorted(conteos, reverse=True)
    assert all(c > 0 for c in conteos)
    # Cada evento declara su familia, que es de donde sale el color de su barra.
    assert all(e["categoria_slug"] for e in datos["eventos"])


def test_el_periodo_provincial_abarca_el_de_sus_distritos(api, datos_muestra):
    """Es un rango **abarcado**, no un periodo común: cada distrito trae el suyo.

    Anunciar «periodo 2003-2025» como si fuera una ventana única sería falso —en la región hay
    21 variantes, de 5 a 23 años—, y por eso viaja también cuántas son.
    """
    import re

    lista = api.get("/api/peligros/frecuencia/?provincia=0801").json()
    datos = api.get("/api/peligros/frecuencia/provincia/0801/").json()

    anios = [
        int(a) for d in lista if d["total"] and d["rango_fecha"]
        for a in re.findall(r"\d{4}", d["rango_fecha"])
    ]
    assert datos["periodo"] == f"{min(anios)}-{max(anios)}"
    assert datos["periodos_distintos"] >= 1


def test_una_provincia_sin_registros_responde_con_ceros_no_404(api, datos_muestra):
    """La provincia existe aunque no haya emergencias: es un estado vacío, no un error."""
    from apps.peligros.models import FrecuenciaEmergencia, TotalDeclaradoEmergencias
    from apps.territorio.models import Provincia

    vacia = next(
        p for p in Provincia.objects.all()
        if not FrecuenciaEmergencia.objects.filter(distrito__provincia=p).exists()
        and not TotalDeclaradoEmergencias.objects.filter(distrito__provincia=p).exists()
    )
    respuesta = api.get(f"/api/peligros/frecuencia/provincia/{vacia.ubigeo}/")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["total"] == 0
    assert datos["eventos"] == [] and datos["familias"] == []
    assert datos["distritos_con_registro"] == 0
    assert datos["periodo"] is None


def test_la_capa_de_emergencias_solo_trae_distritos_con_registro(api, datos_muestra):
    """Un ícono de emergencia sobre un distrito que declara cero afirmaría lo que la fuente calla.

    Y el punto tiene que caer **entre los centros poblados de ese distrito**: no hay geometría
    distrital en el proyecto, así que se deriva de ellos, y esta prueba es lo que impide que un
    cambio en ese cálculo mande los íconos a otra parte de la región sin que nada falle.
    """
    from apps.territorio.models import CentroPoblado

    datos = api.get("/api/peligros/frecuencia/geojson/").json()
    assert datos["type"] == "FeatureCollection"
    assert datos["features"]

    for feature in datos["features"]:
        props = feature["properties"]
        assert props["total"] > 0
        lon, lat = feature["geometry"]["coordinates"]
        ccpp = CentroPoblado.objects.filter(
            distrito__ubigeo=props["ubigeo"]
        ).exclude(lat=None).values_list("lon", "lat")
        lones = [c[0] for c in ccpp]
        lates = [c[1] for c in ccpp]
        assert min(lones) <= lon <= max(lones)
        assert min(lates) <= lat <= max(lates)


def test_la_capa_de_emergencias_respeta_el_ambito(api, datos_muestra):
    """Marcar la casilla no puede sacar al usuario del ámbito que ya eligió."""
    todos = api.get("/api/peligros/frecuencia/geojson/").json()["features"]
    cusco = api.get("/api/peligros/frecuencia/geojson/?provincia=0801").json()["features"]

    assert 0 < len(cusco) < len(todos)
    assert all(f["properties"]["provincia"] == "CUSCO" for f in cusco)


def test_cada_tipo_de_peligro_trae_su_icono(api, datos_muestra):
    """El visor no conoce los peligros: forma del símbolo y etiqueta salen del catálogo.

    Sin ícono en el API el frontend tendría que mantener su propia tabla de 9 entradas, y
    añadir un peligro en el admin exigiría desplegar el frontend para que se viera en el mapa.
    """
    tipos = api.get("/api/peligros/tipos/").json()

    assert len(tipos) == 9
    assert all(t["icono"] for t in tipos), "algún tipo de peligro se quedó sin ícono"
    assert len({t["icono"] for t in tipos}) == 9, "dos peligros comparten ícono"


def test_tipos_de_peligro_traen_slug_color_y_categoria(api):
    """El frontend pinta el semáforo con estos datos; el slug es la clave de los tiles."""
    tipos = api.get("/api/peligros/tipos/").json()
    filas = tipos["results"] if isinstance(tipos, dict) else tipos

    assert len(filas) == 9
    for tipo in filas:
        assert set(tipo) >= {"nombre", "slug", "color", "categoria_geo"}
        assert "-" not in tipo["slug"]
