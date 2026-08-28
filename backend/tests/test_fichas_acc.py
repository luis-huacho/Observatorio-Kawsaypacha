"""La ficha ACC autónoma y su importación por Excel.

Dos cosas se vigilan aquí, y las dos son fallos que no se ven:

- Que una fila mala **no** arrastre al archivo entero, y que una cabecera equivocada sí lo pare:
  con las columnas corridas cada texto se guardaría en el campo de al lado y la ficha quedaría
  plausible pero mal.
- Que el nombre repetido se detecte con el mismo criterio que se le anuncia al usuario —recorte
  y mayúsculas— y **solo para comparar**: lo que se guarda es el texto tal como vino.
"""
import io

from django.urls import reverse

import openpyxl
import pytest

from apps.medidas import importacion
from apps.medidas.models import MedidaFichaACC

pytestmark = pytest.mark.django_db

URL_IMPORTAR = reverse("admin:medidas_medidafichaacc_importar_excel")
URL_PLANTILLA = reverse("admin:medidas_medidafichaacc_descargar_plantilla")


@pytest.fixture(autouse=True)
def temporal_aislado(settings, tmp_path):
    """El Excel a medio importar va a un directorio de la prueba, no al del proyecto.

    Sin esto la suite deja archivos dentro del repositorio: el barrido del admin solo se lleva
    los de más de seis horas, así que se acumulan entre corridas sin que nadie los mire.
    """
    settings.IMPORTACIONES_TMP_DIR = tmp_path / "importaciones"


def _fila(nombre, **cambios):
    """Una fila completa y válida, con el nombre que se le pida."""
    valores = {campo: f"texto de {campo}" for campo in importacion.CAMPOS}
    valores[importacion.CAMPO_NOMBRE] = nombre
    valores.update(cambios)
    return [valores[campo] for campo in importacion.CAMPOS]


def _excel(tmp_path, filas, cabecera=None, nombre="fichas.xlsx"):
    wb = openpyxl.Workbook()
    hoja = wb.active
    hoja.title = importacion.HOJA_DATOS
    hoja.append(cabecera or importacion.columnas_esperadas())
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


def test_un_archivo_limpio_se_previsualiza_y_luego_se_importa(admin_client, tmp_path):
    """La previsualización no escribe nada: recién el segundo POST crea las fichas."""
    ruta = _excel(tmp_path, [_fila("Cosecha de agua en Ccatca"), _fila("Terrazas en Lares")])

    previa = _subir(admin_client, ruta)

    assert previa.status_code == 200
    analisis = previa.context["analisis"]
    assert len(analisis.validas) == 2
    assert analisis.omitidas == []
    assert MedidaFichaACC.objects.count() == 0, "la previsualización no debe escribir"

    _confirmar(admin_client)

    assert MedidaFichaACC.objects.count() == 2
    assert set(MedidaFichaACC.objects.values_list("value_001", flat=True)) == {
        "Cosecha de agua en Ccatca",
        "Terrazas en Lares",
    }


def test_un_nombre_que_ya_existe_se_omite_aunque_cambien_mayusculas_y_espacios(
    admin_client, tmp_path
):
    """El criterio que se le anuncia al usuario es recorte + mayúsculas, y tiene que ser el que
    se aplica: si comparara literal, el mismo proyecto entraría dos veces por un espacio."""
    MedidaFichaACC.objects.create(
        **{campo: "x" for campo in importacion.CAMPOS if campo != importacion.CAMPO_NOMBRE},
        value_001="Cosecha de agua en Ccatca",
    )
    ruta = _excel(tmp_path, [
        _fila("  cosecha DE agua en Ccatca  "),
        _fila("Terrazas en Lares"),
    ])

    previa = _subir(admin_client, ruta)
    analisis = previa.context["analisis"]

    assert [f.numero for f in analisis.omitidas] == [2]
    assert "repetido" in analisis.omitidas[0].motivo
    assert "Cosecha de agua en Ccatca" in analisis.omitidas[0].motivo
    assert [f.nombre for f in analisis.validas] == ["Terrazas en Lares"]

    _confirmar(admin_client)

    assert MedidaFichaACC.objects.count() == 2, "solo entra la que no chocaba"


def test_el_nombre_repetido_dentro_del_mismo_archivo_tambien_se_omite(admin_client, tmp_path):
    """El duplicado no siempre viene de la base: el Excel puede traer la misma ficha dos veces."""
    ruta = _excel(tmp_path, [
        _fila("Cosecha de agua en Ccatca"),
        _fila("COSECHA DE AGUA EN CCATCA"),
    ])

    previa = _subir(admin_client, ruta)
    analisis = previa.context["analisis"]

    assert [f.numero for f in analisis.validas] == [2]
    assert [f.numero for f in analisis.omitidas] == [3]
    assert "fila 2" in analisis.omitidas[0].motivo

    _confirmar(admin_client)

    assert MedidaFichaACC.objects.count() == 1


def test_el_texto_se_guarda_tal_como_vino_no_normalizado(admin_client, tmp_path):
    """La normalización es SOLO para comparar. Guardar en mayúsculas destrozaría el nombre que
    PREDES publica."""
    ruta = _excel(tmp_path, [_fila("  Cosecha de agua en Ccatca  ")])

    _subir(admin_client, ruta)
    _confirmar(admin_client)

    assert MedidaFichaACC.objects.get().value_001 == "Cosecha de agua en Ccatca"


def test_una_fila_sin_campos_obligatorios_se_omite_y_las_demas_entran(admin_client, tmp_path):
    """Una fila mala no puede arrastrar al archivo: el motivo nombra la columna que falta."""
    ruta = _excel(tmp_path, [
        _fila("Sin institución", value_003=""),
        _fila("Completa"),
    ])

    previa = _subir(admin_client, ruta)
    analisis = previa.context["analisis"]

    assert [f.nombre for f in analisis.validas] == ["Completa"]
    assert len(analisis.omitidas) == 1
    assert str(
        MedidaFichaACC._meta.get_field("value_003").verbose_name
    ) in analisis.omitidas[0].motivo

    _confirmar(admin_client)

    assert MedidaFichaACC.objects.count() == 1


def test_los_campos_opcionales_pueden_venir_vacios(admin_client, tmp_path):
    """002, 004 y 008 son `blank=True` en el modelo; exigirlos al importar sería inventar una
    regla que el formulario del admin no aplica."""
    ruta = _excel(tmp_path, [_fila("Con huecos", value_002="", value_004="", value_008="")])

    previa = _subir(admin_client, ruta)

    assert previa.context["analisis"].omitidas == []


def test_una_cabecera_distinta_no_importa_nada_y_dice_que_esperaba(admin_client, tmp_path):
    """Con las columnas corridas cada texto caería en el campo de al lado: la ficha se vería
    llena y estaría mal. Por eso la cabecera sí aborta el archivo entero."""
    columnas = importacion.columnas_esperadas()
    columnas[4] = "Otra cosa"
    ruta = _excel(tmp_path, [_fila("Cosecha de agua en Ccatca")], cabecera=columnas)

    respuesta = _subir(admin_client, ruta)

    assert respuesta.status_code == 200
    assert "analisis" not in respuesta.context
    assert "no tiene las 17 columnas esperadas" in respuesta.context["error"]
    assert columnas[4] in respuesta.context["error"], "tiene que decir qué encontró"
    assert MedidaFichaACC.objects.count() == 0


def test_la_cabecera_tolera_espacios_de_mas_y_tildes_perdidas(admin_client, tmp_path):
    """Son preguntas largas que el usuario copia y pega; un doble espacio no puede costarle la
    importación. Los datos no se tocan, solo la comparación de la cabecera."""
    columnas = [c.replace(" ", "  ").replace("á", "a") for c in importacion.columnas_esperadas()]
    ruta = _excel(tmp_path, [_fila("Cosecha de agua en Ccatca")], cabecera=columnas)

    previa = _subir(admin_client, ruta)

    assert len(previa.context["analisis"].validas) == 1


def test_las_filas_en_blanco_del_final_no_cuentan_como_error(admin_client, tmp_path):
    """Excel arrastra filas vacías al guardar; anunciarlas como omitidas asustaría sin motivo."""
    ruta = _excel(tmp_path, [_fila("Cosecha de agua en Ccatca"), [""] * 17, [None] * 17])

    previa = _subir(admin_client, ruta)
    analisis = previa.context["analisis"]

    assert analisis.total == 1
    assert analisis.omitidas == []


def test_confirmar_sin_haber_subido_nada_no_crea_fichas(admin_client):
    """Sin token en sesión no hay qué importar: es el usuario que vuelve atrás con el navegador."""
    respuesta = _confirmar(admin_client)

    assert MedidaFichaACC.objects.count() == 0
    assert any("caducó" in str(m) for m in respuesta.context["messages"])


def test_el_temporal_se_consume_una_sola_vez(admin_client, tmp_path):
    """Recargar la confirmación no puede duplicar la carga: el archivo se borra al aplicarla."""
    ruta = _excel(tmp_path, [_fila("Cosecha de agua en Ccatca")])
    _subir(admin_client, ruta)

    _confirmar(admin_client)
    _confirmar(admin_client)

    assert MedidaFichaACC.objects.count() == 1


def test_la_plantilla_descargada_se_puede_volver_a_importar(admin_client, tmp_path):
    """La prueba redonda: si la plantilla y el validador se separan, esto lo dice. Los dos leen
    los verbose_name del modelo, así que solo pueden separarse por accidente."""
    descarga = admin_client.get(URL_PLANTILLA)

    assert descarga.status_code == 200
    assert descarga["Content-Disposition"].endswith('filename="plantilla-fichas-acc.xlsx"')

    wb = openpyxl.load_workbook(io.BytesIO(descarga.content))
    assert wb.worksheets[0].title == importacion.HOJA_DATOS
    wb.worksheets[0].append(_fila("Cosecha de agua en Ccatca"))
    ruta = tmp_path / "plantilla-llena.xlsx"
    wb.save(ruta)

    previa = _subir(admin_client, ruta)

    assert len(previa.context["analisis"].validas) == 1


def test_un_archivo_que_no_es_excel_no_revienta(admin_client, tmp_path):
    """openpyxl lanza excepciones de todo tipo ante un archivo cualquiera; el usuario tiene que
    ver un mensaje, no un 500."""
    ruta = tmp_path / "falso.xlsx"
    ruta.write_bytes(b"esto no es un Excel")

    respuesta = _subir(admin_client, ruta)

    assert respuesta.status_code == 200
    assert "No se pudo leer el archivo" in respuesta.context["error"]


def test_sin_permiso_de_alta_no_se_llega_a_importar(client, django_user_model):
    """Importar es crear fichas en lote: exige el mismo permiso que el botón «Añadir».

    El usuario es de staff pero sin grupos: si la comprobación se cayera, entrar al admin
    bastaría para cargar fichas a mansalva. El grupo Editor sí tiene el permiso, así que la
    prueba no puede apoyarse en él."""
    usuario = django_user_model.objects.create_user(
        username="mirona", password="x", is_staff=True
    )
    client.force_login(usuario)

    assert not usuario.has_perm("medidas.add_medidafichaacc")
    assert client.get(URL_IMPORTAR).status_code == 403
    assert client.get(URL_PLANTILLA).status_code == 403


def test_la_ficha_ya_no_pide_una_medida(admin_client):
    """El formulario de alta perdió el campo «Medida» — y el modelo, la columna."""
    respuesta = admin_client.get(reverse("admin:medidas_medidafichaacc_add"))

    assert respuesta.status_code == 200
    assert "medida" not in respuesta.context["adminform"].form.fields
    assert not [f.name for f in MedidaFichaACC._meta.get_fields() if f.name == "medida"]
