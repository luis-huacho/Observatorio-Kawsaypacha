"""Importación de normativa desde Excel.

El segundo caso de ADR-D9, y el primero en el que **la hoja no son los campos del modelo**: en
fichas ACC las 17 columnas son 17 `TextField` y basta con recortar el texto. Aquí hay tres
deducciones —tipo, ámbito y fecha— y ahí es donde están los fallos que no se ven:

- Un tipo o una entidad que no casan **no pueden replegarse a un valor por defecto**: dejarían la
  norma clasificada como algo que nadie decidió, con aspecto de dato bueno.
- El Excel trae un año y el modelo pide una fecha. Se fija al 1 de enero y **se dice**; lo que no
  puede es caer a hoy, que es la fecha que parece cierta y no lo es.
- La unicidad se decide por «Nombre», con el mismo criterio que se le anuncia al usuario —recorte
  y mayúsculas— y **solo para comparar**: lo que se guarda es el texto tal como vino.
"""
import datetime as dt

from django.urls import reverse

import openpyxl
import pytest

from apps.normativa import importacion
from apps.normativa.models import EntidadEmisora, Norma, TipoNorma

pytestmark = pytest.mark.django_db

URL_IMPORTAR = reverse("admin:normativa_norma_importar_excel")
URL_PLANTILLA = reverse("admin:normativa_norma_descargar_plantilla")


@pytest.fixture(autouse=True)
def temporal_aislado(settings, tmp_path):
    """El Excel a medio importar va a un directorio de la prueba, no al del proyecto."""
    settings.IMPORTACIONES_TMP_DIR = tmp_path / "importaciones"



def _tipo(slug: str) -> TipoNorma:
    """El tipo del catálogo, que siembra `seed --solo-catalogos` para toda la sesión."""
    return TipoNorma.objects.get(slug=slug)


@pytest.fixture
def entidades():
    """Tres entidades del catálogo, una por ámbito. El importador nunca las crea.

    `get_or_create` y no `create`: el catálogo puede venir ya sembrado por la migración de datos,
    y `nombre` es único.
    """
    def entidad(nombre, sigla, slug):
        obj, _ = EntidadEmisora.objects.get_or_create(
            nombre=nombre, defaults={"sigla": sigla, "slug": slug}
        )
        return obj

    return {
        "nacional": entidad("Presidencia del Consejo de Ministros", "PCM", "pcm"),
        "regional": entidad("Gobierno Regional de Cusco", "GORE Cusco", "gore-cusco"),
        "local": entidad("Municipalidad Provincial del Cusco", "MPC", "mpc"),
    }


def _fila(nombre, **cambios):
    """Una fila completa y válida, con el nombre que se le pida."""
    valores = {
        "N": 1,
        "Tipo de normativa": "Decreto Supremo",
        "Nombre": nombre,
        "Descripción": "Aprueba el reglamento de la ley del SINAGERD.",
        "Entidad autora": "Presidencia del Consejo de Ministros",
        "Año de publicación": 2011,
        "Link": "https://www.gob.pe/norma",
    }
    valores.update(cambios)
    return [valores[c] for c in importacion.COLUMNAS]


def _excel(tmp_path, filas, cabecera=None, nombre="normas.xlsx"):
    wb = openpyxl.Workbook()
    hoja = wb.active
    hoja.title = importacion.HOJA_DATOS
    hoja.append(list(cabecera or importacion.COLUMNAS))
    for fila in filas:
        hoja.append(fila)
    ruta = tmp_path / nombre
    wb.save(ruta)
    return ruta


def _subir(cliente, ruta):
    with ruta.open("rb") as fh:
        return cliente.post(URL_IMPORTAR, {"archivo": fh})


def _confirmar(cliente):
    return cliente.post(URL_IMPORTAR, {"confirmar": "1"}, follow=True)


# --- El camino feliz, y que la previa no escribe ----------------------------


def test_un_archivo_limpio_se_previsualiza_y_luego_se_importa(admin_client, tmp_path, entidades):
    ruta = _excel(tmp_path, [_fila("Ley 29664"), _fila("DS 048-2011-PCM")])

    respuesta = _subir(admin_client, ruta)

    assert respuesta.status_code == 200
    analisis = respuesta.context["analisis"]
    assert len(analisis.validas) == 2
    assert analisis.omitidas == []
    # La previa no escribe: es lo que hace que la confirmación signifique algo.
    assert Norma.objects.count() == 0

    _confirmar(admin_client)

    assert Norma.objects.count() == 2


def test_lo_importado_queda_en_borrador_y_con_todo_lo_deducido(admin_client, tmp_path, entidades):
    """Nada se publica solo: entra como borrador y una persona lo revisa."""
    ruta = _excel(tmp_path, [_fila("DS 048-2011-PCM")])

    _subir(admin_client, ruta)
    _confirmar(admin_client)

    norma = Norma.objects.get()
    assert norma.estado == Norma.Estado.BORRADOR
    assert norma.titulo == "DS 048-2011-PCM"
    assert norma.tipo.slug == "ds"
    assert norma.ambito == Norma.Ambito.NACIONAL
    assert norma.entidad_emisora == entidades["nacional"]
    assert norma.fecha == dt.date(2011, 1, 1)
    assert norma.url_oficial == "https://www.gob.pe/norma"
    assert norma.resumen.startswith("Aprueba el reglamento")
    assert norma.slug


# --- La unicidad por «Nombre», que es lo que se pidió -----------------------


def test_un_nombre_que_ya_existe_se_omite_aunque_cambien_mayusculas_y_espacios(
    admin_client, tmp_path, entidades
):
    Norma.objects.create(
        titulo="Ley N° 29664", slug="ley-29664", tipo=_tipo("ley"),
        ambito=Norma.Ambito.NACIONAL, fecha=dt.date(2011, 2, 19), resumen="…",
    )
    ruta = _excel(tmp_path, [_fila("  ley n° 29664  "), _fila("DS 048-2011-PCM")])

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert len(analisis.validas) == 1
    assert len(analisis.omitidas) == 1
    assert "repetido" in analisis.omitidas[0].motivo
    assert "Ley N° 29664" in analisis.omitidas[0].motivo


def test_el_nombre_repetido_dentro_del_mismo_archivo_tambien_se_omite(
    admin_client, tmp_path, entidades
):
    """Dos filas iguales en el mismo Excel son tan duplicado como una contra la base."""
    ruta = _excel(tmp_path, [_fila("Ley 29664"), _fila("LEY 29664")])

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert [f.numero for f in analisis.validas] == [2]
    assert [f.numero for f in analisis.omitidas] == [3]
    assert "fila 2" in analisis.omitidas[0].motivo


def test_el_nombre_se_guarda_tal_como_vino(admin_client, tmp_path, entidades):
    """La normalización es **solo para comparar**: el título no se toca (salvo el recorte)."""
    ruta = _excel(tmp_path, [_fila("  Ley N° 29664 — SINAGERD  ")])

    _subir(admin_client, ruta)
    _confirmar(admin_client)

    assert Norma.objects.get().titulo == "Ley N° 29664 — SINAGERD"


# --- La cabecera aborta el archivo entero ----------------------------------


def test_una_cabecera_distinta_no_importa_nada_y_dice_que_esperaba(
    admin_client, tmp_path, entidades
):
    """Con las columnas corridas, cada valor entraría en el campo de al lado.

    La norma quedaría plausible y mal —el tipo en el nombre, la entidad en la descripción— sin
    que nada lo delatara después. Por eso la cabecera es lo único que aborta el archivo.
    """
    cabecera = list(importacion.COLUMNAS)
    cabecera[2] = "Título"
    ruta = _excel(tmp_path, [_fila("Ley 29664")], cabecera=cabecera)

    respuesta = _subir(admin_client, ruta)

    assert "analisis" not in respuesta.context
    assert "no tiene las 7 columnas esperadas" in respuesta.context["error"]
    assert "Título" in respuesta.context["error"]
    assert Norma.objects.count() == 0


def test_la_cabecera_tolera_espacios_de_mas_y_tildes_perdidas(admin_client, tmp_path, entidades):
    """El usuario reescribe la cabecera a mano; una tilde no puede costarle la importación."""
    cabecera = [c.replace(" ", "  ").replace("ó", "o").replace("Á", "A") for c in importacion.COLUMNAS]
    ruta = _excel(tmp_path, [_fila("Ley 29664")], cabecera=cabecera)

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert len(analisis.validas) == 1


def test_las_filas_en_blanco_del_final_no_cuentan_como_error(admin_client, tmp_path, entidades):
    ruta = _excel(tmp_path, [_fila("Ley 29664"), [""] * 7, [None] * 7])

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert analisis.total == 1
    assert analisis.omitidas == []


# --- Las tres deducciones --------------------------------------------------


@pytest.mark.parametrize(
    "escrito,slug_esperado",
    [
        ("Ley", "ley"),
        ("Decreto Supremo", "ds"),
        ("D.S.", "ds"),
        ("decreto  supremo", "ds"),
        ("Resolución Ministerial", "rm"),
        ("RESOLUCION JEFATURAL", "rj"),
        ("Ordenanza Regional", "ordenanza"),
        ("Ordenanza Municipal", "ordenanza"),
    ],
)
def test_el_tipo_se_reconoce_sin_tildes_ni_mayusculas(
    admin_client, tmp_path, entidades, escrito, slug_esperado
):
    """Las ocho variantes salen del catálogo: nombre, abreviatura y sinónimos.

    Las cuatro que no son ni el nombre ni la sigla —«D.S.», «Ordenanza Regional»…— dependen de que
    la semilla haya trasladado los sinónimos que antes vivían en una tabla fija del importador.
    """
    ruta = _excel(tmp_path, [_fila("Una norma", **{"Tipo de normativa": escrito})])

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert analisis.validas[0].valores["tipo"].slug == slug_esperado


def test_un_tipo_fuera_del_catalogo_omite_la_fila_en_vez_de_elegir_uno(
    admin_client, tmp_path, entidades
):
    """Replegar a una opción falsa clasificaría la norma como algo que nadie decidió.

    Se omite y se dice cuál era, para poder decidir con el archivo delante si hay que ampliar el
    catálogo. Es la misma regla de ADR-D8: antes vacío que una opción inventada.
    """
    ruta = _excel(tmp_path, [_fila("Una norma", **{"Tipo de normativa": "Acuerdo de Concejo"})])

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert analisis.validas == []
    assert "Acuerdo de Concejo" in analisis.omitidas[0].motivo
    assert "tipo" in analisis.omitidas[0].motivo.lower()


@pytest.mark.parametrize(
    "escrito,clave",
    [
        ("Presidencia del Consejo de Ministros", "nacional"),
        ("PCM", "nacional"),
        ("  presidencia del consejo de ministros ", "nacional"),
        ("Gobierno Regional de Cusco", "regional"),
        ("GORE Cusco", "regional"),
        ("Municipalidad Provincial del Cusco", "local"),
    ],
)
def test_la_entidad_casa_contra_el_catalogo_por_nombre_o_sigla(
    admin_client, tmp_path, entidades, escrito, clave
):
    ruta = _excel(tmp_path, [_fila("Una norma", **{"Entidad autora": escrito})])

    fila = _subir(admin_client, ruta).context["analisis"].validas[0]

    assert fila.valores["entidad_emisora"] == entidades[clave]


def test_una_entidad_que_no_esta_en_el_catalogo_omite_la_fila_y_no_la_crea(
    admin_client, tmp_path, entidades
):
    """ADR-D11 fija que el catálogo lo mantiene una persona: «la IA elige y nunca crea».

    Un importador tiene menos derecho todavía: crear entidades al vuelo desde una hoja de cálculo
    es exactamente cómo «PCM», «P.C.M.» y «Presidencia del Consejo de Ministros» acaban siendo
    tres filas y el filtro del listado deja de servir.
    """
    ruta = _excel(tmp_path, [_fila("Una norma", **{"Entidad autora": "Comité de Gestión Local"})])

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert analisis.validas == []
    assert "Comité de Gestión Local" in analisis.omitidas[0].motivo
    assert not EntidadEmisora.objects.filter(nombre="Comité de Gestión Local").exists()


def test_la_pantalla_agrupa_las_entidades_que_faltan_para_crearlas_de_una_vez(
    admin_client, tmp_path, entidades
):
    """Descubrirlas de una en una obligaría a subir el archivo tantas veces como falten.

    Y la concordancia se comprueba: «Faltan 1 entidad» es el descuido que delata una pantalla
    generada, y con una sola entidad ausente es el caso más probable.
    """
    ruta = _excel(
        tmp_path,
        [
            _fila("Una", **{"Entidad autora": "Comité Vecinal"}),
            _fila("Otra", **{"Entidad autora": "Comité Vecinal"}),
            _fila("Tercera", **{"Entidad autora": "Mesa de Concertación"}),
        ],
    )

    respuesta = _subir(admin_client, ruta)

    # Sin repetir: son dos entidades distintas en tres filas.
    assert respuesta.context["analisis"].entidades_desconocidas == [
        "Comité Vecinal",
        "Mesa de Concertación",
    ]
    assert "Faltan 2 entidades en el catálogo" in respuesta.content.decode()


def test_con_una_sola_entidad_ausente_la_pantalla_concuerda_en_singular(
    admin_client, tmp_path, entidades
):
    ruta = _excel(tmp_path, [_fila("Una", **{"Entidad autora": "Comité Vecinal"})])

    contenido = _subir(admin_client, ruta).content.decode()

    assert "Falta 1 entidad en el catálogo" in contenido


def test_el_ambito_sale_de_la_entidad_ya_casada_y_no_del_texto_libre(
    admin_client, tmp_path, entidades
):
    """El ámbito es obligatorio y no viene en la hoja: se deduce del nombre canónico.

    Del canónico y no de lo que escribió el usuario, que puede venir como sigla («MPC» no dice
    que sea una municipalidad).
    """
    ruta = _excel(
        tmp_path,
        [
            _fila("Nacional", **{"Entidad autora": "PCM"}),
            _fila("Regional", **{"Entidad autora": "GORE Cusco"}),
            _fila("Local", **{"Entidad autora": "MPC"}),
        ],
    )

    ambitos = [f.valores["ambito"] for f in _subir(admin_client, ruta).context["analisis"].validas]

    assert ambitos == [Norma.Ambito.NACIONAL, Norma.Ambito.REGIONAL, Norma.Ambito.LOCAL]


def test_una_entidad_del_catalogo_cuyo_ambito_no_se_deduce_omite_la_fila(
    admin_client, tmp_path, entidades
):
    """El catálogo lo amplía PREDES, así que puede entrar una entidad que las reglas no cubren.

    Falla en alto: la fila se omite con su motivo, en vez de colar un «nacional» por defecto que
    nadie decidió y que ya no se distingue de uno correcto.
    """
    EntidadEmisora.objects.create(nombre="Comunidad Campesina de Ccatca", slug="ccatca")
    ruta = _excel(
        tmp_path, [_fila("Una norma", **{"Entidad autora": "Comunidad Campesina de Ccatca"})]
    )

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert analisis.validas == []
    assert "ámbito" in analisis.omitidas[0].motivo


def test_el_anio_se_convierte_al_uno_de_enero_y_nunca_a_hoy(admin_client, tmp_path, entidades):
    """El Excel trae un año y el modelo pide una fecha. Es lo que ya decidió ADR-D10.

    Un año ilegible **no** cae a hoy: sería la única fecha del sistema que parece cierta sin
    serlo, y no habría forma de distinguirla de una cargada a mano.
    """
    ruta = _excel(
        tmp_path,
        [
            _fila("Con año", **{"Año de publicación": 2019}),
            _fila("Año como texto", **{"Año de publicación": " 2020 "}),
            _fila("Sin año", **{"Año de publicación": "sin fecha"}),
            _fila("Año imposible", **{"Año de publicación": 1200}),
        ],
    )

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert [f.valores["fecha"] for f in analisis.validas] == [
        dt.date(2019, 1, 1),
        dt.date(2020, 1, 1),
    ]
    assert len(analisis.omitidas) == 2
    assert all("año" in f.motivo.lower() for f in analisis.omitidas)
    assert dt.date.today() not in [f.valores["fecha"] for f in analisis.validas]


def test_una_descripcion_larga_entra_recortada_y_se_declara(admin_client, tmp_path, entidades):
    """`resumen` tope a 700. Omitir la fila perdería una norma buena por un tope de campo."""
    ruta = _excel(tmp_path, [_fila("Larga", **{"Descripción": "x" * 900})])

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert len(analisis.validas[0].valores["resumen"]) == 700
    assert analisis.validas[0].avisos
    assert any("recort" in a for a in analisis.validas[0].avisos)


def test_las_columnas_obligatorias_vacias_omiten_la_fila(admin_client, tmp_path, entidades):
    ruta = _excel(tmp_path, [_fila("Sin descripción", **{"Descripción": ""}), _fila("Buena")])

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert [f.nombre for f in analisis.validas] == ["Buena"]
    assert "Descripción" in analisis.omitidas[0].motivo


def test_el_link_es_opcional(admin_client, tmp_path, entidades):
    ruta = _excel(tmp_path, [_fila("Sin enlace", **{"Link": ""})])

    _subir(admin_client, ruta)
    _confirmar(admin_client)

    assert Norma.objects.get().url_oficial in ("", None)


# --- Slugs -----------------------------------------------------------------


def test_dos_filas_con_el_mismo_slug_base_no_chocan(admin_client, tmp_path, entidades):
    """`slug` es único y `slug_unico()` consulta la base por candidato.

    Con `bulk_create` no vería las colisiones **dentro del mismo archivo**, así que los slugs se
    reservan en memoria. Sin esto, dos títulos que solo difieren en la puntuación revientan la
    transacción entera y no entra ninguna norma.
    """
    Norma.objects.create(
        titulo="Ley 29664", slug="ley-29664", tipo=_tipo("ley"),
        ambito=Norma.Ambito.NACIONAL, fecha=dt.date(2011, 1, 1), resumen="…",
    )
    ruta = _excel(tmp_path, [_fila("Ley 29664!"), _fila("¿Ley 29664?")])

    _subir(admin_client, ruta)
    _confirmar(admin_client)

    slugs = list(Norma.objects.values_list("slug", flat=True))
    assert len(slugs) == len(set(slugs)) == 3


# --- La fontanería compartida ----------------------------------------------


def test_confirmar_sin_haber_subido_nada_no_crea_normas(admin_client):
    respuesta = _confirmar(admin_client)

    assert Norma.objects.count() == 0
    assert any("caducó" in str(m) for m in respuesta.context["messages"])


def test_el_temporal_se_consume_una_sola_vez(admin_client, tmp_path, entidades):
    _subir(admin_client, _excel(tmp_path, [_fila("Ley 29664")]))

    _confirmar(admin_client)
    _confirmar(admin_client)

    assert Norma.objects.count() == 1


def test_un_archivo_que_no_es_excel_no_revienta(admin_client, tmp_path):
    ruta = tmp_path / "normas.xlsx"
    ruta.write_bytes(b"esto no es un Excel")

    respuesta = _subir(admin_client, ruta)

    assert respuesta.status_code == 200
    assert "No se pudo leer el archivo" in respuesta.context["error"]


def test_la_plantilla_descargada_se_puede_volver_a_importar(admin_client, tmp_path, entidades):
    """La prueba redonda: si la plantilla y el validador se separan, esto se entera."""
    respuesta = admin_client.get(URL_PLANTILLA)

    assert respuesta.status_code == 200
    assert "attachment" in respuesta["Content-Disposition"]

    ruta = tmp_path / "plantilla.xlsx"
    ruta.write_bytes(respuesta.content)
    wb = openpyxl.load_workbook(ruta)
    assert wb.worksheets[0].title == importacion.HOJA_DATOS
    wb.worksheets[0].append(_fila("Una norma de prueba"))
    wb.save(ruta)

    analisis = _subir(admin_client, ruta).context["analisis"]

    assert len(analisis.validas) == 1


def test_sin_permiso_de_alta_no_se_llega_a_importar(client, django_user_model):
    usuario = django_user_model.objects.create_user(
        username="mirón", password="x", is_staff=True
    )
    assert not usuario.has_perm("normativa.add_norma")
    client.force_login(usuario)

    assert client.get(URL_IMPORTAR).status_code == 403
    assert client.get(URL_PLANTILLA).status_code == 403
