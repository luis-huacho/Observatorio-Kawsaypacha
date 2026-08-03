"""Importadores de Excel (spec 03 y plan de pruebas 08).

Cada caso protege una decisión que salió de la auditoría de los datos reales y que **un refactor
puede deshacer sin que nada falle a la vista**: los datos siguen entrando, el importador sigue
diciendo «activo», y la cifra que se publica es otra. Esa es la razón de ser de este módulo.
"""
from django.utils.text import slugify

import openpyxl
import pytest

from tests.rutas import MUESTRA_FRECUENCIA, MUESTRA_NIVEL

pytestmark = pytest.mark.django_db


def _advertencias(upload) -> str:
    """Todas las advertencias en un solo texto, para buscar por contenido."""
    return "\n".join(upload.log.get("advertencias", []))


# --- Nivel de peligro ------------------------------------------------------


def test_importa_y_queda_activo(importar):
    from apps.datasets.models import DatasetUpload
    from apps.peligros.models import ClasificacionPeligro

    upload = importar()

    assert upload.estado == DatasetUpload.Estado.ACTIVO
    assert ClasificacionPeligro.objects.exists()
    assert upload.log["centros_poblados"] > 0


@pytest.mark.parametrize(
    "hoja, nombre, slug",
    [
        ("Lluvias", "Lluvias intensas", "lluvias_intensas"),
        ("Incendios Forestales", "Incendios forestales", "incendios_forestales"),
    ],
)
def test_el_nombre_del_peligro_sale_del_catalogo_no_del_titulo_de_la_hoja(
    importar, hoja, nombre, slug
):
    """Dos hojas se llaman distinto de lo que dice su columna PELIGRO.

    El catálogo canónico resuelve las dos. Si un refactor derivara el peligro del título de la
    hoja, aparecerían un «Lluvias» y un «Incendios Forestales» fantasma, con slug distinto, y el
    visor perdería esas dos capas del semáforo sin que ningún otro sitio fallara.
    """
    from apps.peligros.models import ClasificacionPeligro, TipoPeligro

    importar()

    assert TipoPeligro.objects.filter(slug=slug, nombre=nombre).exists()
    assert ClasificacionPeligro.objects.filter(tipo_peligro__slug=slug).exists()
    # Ni el nombre tal como lo escribe la hoja, ni el slug que saldría de aplicarle `slugify`.
    assert not TipoPeligro.objects.filter(nombre=hoja).exists()
    assert not TipoPeligro.objects.filter(slug=slugify(hoja)).exists()


def test_un_peligro_fuera_del_catalogo_se_descarta_citando_la_fila(importar, tmp_path):
    """La discrepancia hoja/columna está en el catálogo; un valor **desconocido** no.

    Se descarta la clasificación y se dice dónde estaba, que es lo que permite corregir el Excel.
    """
    inventado = tmp_path / "inventado.xlsx"
    wb = openpyxl.load_workbook(MUESTRA_NIVEL)
    wb["Sismo"].cell(row=2, column=11).value = "Terremoto"
    wb.save(inventado)

    upload = importar(archivo=inventado)

    assert "PELIGRO 'Terremoto' no está en el catálogo" in _advertencias(upload)


def test_ningun_slug_de_peligro_lleva_guion():
    """Es la clave de las propiedades `nivel_<slug>` del tile.

    Con guion medio el visor deja de pintar el semáforo y **ninguna otra prueba lo nota**: el
    API responde, la tabla lista y el mapa sale en gris.
    """
    from apps.peligros.models import TipoPeligro

    slugs = list(TipoPeligro.objects.values_list("slug", flat=True))

    assert slugs, "el seed de catálogos no dejó tipos de peligro"
    assert not [s for s in slugs if "-" in s]


def test_filas_sin_nivel_se_descartan_y_se_cuentan(importar):
    """Sin nivel no hay semáforo, y asumir «1» sería inventar el dato."""
    from apps.peligros.models import ClasificacionPeligro

    upload = importar()

    assert upload.log["descartadas_sin_nivel"] > 0
    assert "sin NIVEL_PELI" in _advertencias(upload)
    assert not ClasificacionPeligro.objects.filter(nivel=None).exists()
    assert set(ClasificacionPeligro.objects.values_list("nivel", flat=True)) <= {1, 2, 3, 4}


def test_filas_sin_codigo_se_descartan_con_aviso(importar):
    upload = importar()

    assert upload.log["descartadas_sin_codigo"] == 2
    assert "sin CODIGO" in _advertencias(upload)


def test_al_deduplicar_gana_el_valor_no_vacio(importar):
    """SICUANI trae DISTRITO en blanco en una hoja y lleno en otra.

    Quedarse con el primero que aparece deja el resultado a merced del orden de las hojas: el
    centro poblado más poblado de Canchis se quedaría sin distrito.
    """
    from apps.territorio.models import CentroPoblado

    importar()
    sicuani = CentroPoblado.objects.get(codigo="0806010001")

    assert sicuani.distrito is not None
    assert sicuani.distrito.nombre.upper().startswith("SICUANI")


def test_se_normalizan_las_dos_grafias_de_la_fuente(importar):
    """`CENEPRED_SIGRID` y `SIGRID_CENEPRED` son la misma fuente escrita al revés.

    Sin normalizar quedan dos filas en el catálogo de fuentes y la ficha de un centro poblado
    cita una u otra según de qué hoja salió su clasificación.
    """
    from apps.peligros.models import Fuente

    importar()
    nombres = set(Fuente.objects.values_list("nombre", flat=True))

    assert "CENEPRED_SIGRID" not in nombres
    assert "SIGRID_CENEPRED" in nombres


def test_ubigeo_derivado_del_codigo_inei(importar):
    """El Excel no trae ubigeo: sale de los 6 primeros dígitos del código de 10."""
    from apps.territorio.models import CentroPoblado

    importar()

    for ccpp in CentroPoblado.objects.select_related("distrito__provincia")[:20]:
        assert ccpp.codigo.startswith(ccpp.distrito.ubigeo)
        assert ccpp.distrito.ubigeo.startswith(ccpp.distrito.provincia.ubigeo)


# --- Frecuencia de emergencias ---------------------------------------------


def test_adr_d1_cusco_se_guarda_como_declarado(datos_muestra):
    """El caso que motivó ADR-D1.

    CUSCO trae los cuatro subtotales llenos (TOTAL 134) y **todas** las columnas de evento
    vacías. Descartar los `TOT_*` —lo que hacía la primera versión— dejaba a la capital regional
    publicando «0 emergencias», que es peor que no publicar nada.
    """
    from apps.peligros.models import FrecuenciaEmergencia, TotalDeclaradoEmergencias
    from apps.territorio.models import Distrito

    cusco = Distrito.objects.get(ubigeo="080101")
    declarados = TotalDeclaradoEmergencias.objects.filter(distrito=cusco)

    assert not FrecuenciaEmergencia.objects.filter(distrito=cusco).exists()
    assert declarados.count() == 4
    assert sum(declarados.values_list("total", flat=True)) == 134


def test_cuando_hay_desglose_el_declarado_no_se_guarda(datos_muestra):
    """Regla literal del ADR-D1: el desglose manda y el declarado solo se registra si descuadra.

    Guardar los dos haría ambiguo el `desglose_disponible` del API, que es lo que la interfaz usa
    para decidir si dibuja el gráfico o explica que la fuente no desagrega.
    """
    from apps.peligros.models import FrecuenciaEmergencia, TotalDeclaradoEmergencias
    from apps.territorio.models import Distrito

    ollanta = Distrito.objects.get(nombre__iexact="OLLANTAYTAMBO")

    assert FrecuenciaEmergencia.objects.filter(distrito=ollanta).exists()
    assert not TotalDeclaradoEmergencias.objects.filter(distrito=ollanta).exists()


def test_descuadre_de_subtotal_prevalece_el_desglose(datos_muestra):
    """SANGARARÁ declara 18 meteorológicos y su desglose suma 27.

    Se conserva el desglose —es el dato con detalle— y la diferencia queda en el log para que
    PREDES pueda llevársela a la fuente. Silenciarla sería publicar una cifra que la propia
    fuente contradice.
    """
    from apps.peligros.models import FrecuenciaEmergencia
    from apps.territorio.models import Distrito

    upload = datos_muestra["frecuencia"]
    sangarara = Distrito.objects.get(nombre__iexact="SANGARARA")
    meteorologicos = FrecuenciaEmergencia.objects.filter(
        distrito=sangarara, tipo_evento__categoria__slug="meteorologico"
    )

    assert sum(meteorologicos.values_list("conteo", flat=True)) == 27
    assert "el subtotal declarado de 'meteorologico' es 18" in _advertencias(upload)
    assert "Prevalece el desglose" in _advertencias(upload)


def test_distrito_del_padron_sin_fila_avisa_y_no_aborta(datos_muestra):
    """En el archivo real es ACOMAYO; en la muestra, cualquier distrito del padrón sin fila.

    Lo que se prueba es la política, no el nombre: un distrito ausente **avisa y no aborta**.
    Abortar dejaría los otros 111 sin importar, y asumir 0 lo publicaría como distrito sin
    emergencias. El caso concreto de ACOMAYO va en la prueba `lento` sobre el archivo completo.
    """
    from apps.datasets.models import DatasetUpload
    from apps.territorio.models import Distrito

    upload = datos_muestra["frecuencia"]
    con_fila = {"CUSCO", "SANGARARA", "MOLLEPATA", "OLLANTAYTAMBO", "ACOPIA"}
    esperados = [
        d.nombre for d in Distrito.objects.all() if d.nombre.upper() not in con_fila
    ]

    assert upload.estado == DatasetUpload.Estado.ACTIVO
    assert esperados, "la muestra no dejó ningún distrito sin fila que comprobar"
    assert "no tienen fila en el Excel" in _advertencias(upload)
    assert len(upload.log["distritos_sin_fila"]) == len(esperados)
    for nombre in esperados:
        assert any(nombre in fila for fila in upload.log["distritos_sin_fila"])


def test_fila_vacia_no_es_lo_mismo_que_declarar_subtotales(datos_muestra):
    """ACOPIA tiene fila y ni un solo número: 21 distritos así en el archivo real.

    No es «declara subtotales sin desagregar» (ADR-D1) ni «declara cero». No hay dato, y el API
    responderá 404 igual que para ACOMAYO — así que tiene que quedar contado aparte, o 21
    distritos sin información se esconden detrás de un aviso que dice otra cosa.
    """
    from apps.peligros.models import FrecuenciaEmergencia, TotalDeclaradoEmergencias
    from apps.territorio.models import Distrito

    upload = datos_muestra["frecuencia"]
    acopia = Distrito.objects.get(nombre__iexact="ACOPIA")

    assert not FrecuenciaEmergencia.objects.filter(distrito=acopia).exists()
    assert not TotalDeclaradoEmergencias.objects.filter(distrito=acopia).exists()
    assert any("ACOPIA" in a for a in upload.log["distritos_sin_dato"])
    assert "ni un solo dato" in _advertencias(upload)


def test_el_rango_de_fechas_se_normaliza_pero_no_se_reinterpreta(datos_muestra):
    """`2003 - 2022` y `2003-2022` son el mismo periodo escrito de dos formas (23 variantes).

    Se quitan los espacios y nada más: convertirlo a dos enteros perdería los valores que no son
    un rango simple, y el periodo es lo que impide comparar distritos a ciegas.
    """
    from apps.peligros.models import TotalDeclaradoEmergencias

    declarado = TotalDeclaradoEmergencias.objects.filter(distrito__ubigeo="080101").first()

    assert declarado.rango_fecha == "2003-2022"


def test_la_fuente_invertida_se_normaliza_y_se_registra(datos_muestra):
    from apps.peligros.models import TotalDeclaradoEmergencias

    upload = datos_muestra["frecuencia"]
    declarado = TotalDeclaradoEmergencias.objects.filter(distrito__ubigeo="080101").first()

    assert declarado.fuente == "SIGRID_CENEPRED"
    assert "se normaliza a 'SIGRID_CENEPRED'" in _advertencias(upload)


# --- Garantías transversales ----------------------------------------------


def test_todo_o_nada_un_archivo_invalido_no_toca_los_datos_activos(importar, tmp_path):
    """Un Excel con las columnas cambiadas deja los datos anteriores intactos.

    Es la garantía que permite a PREDES probar un archivo sin miedo: o entra completo, o no entra.
    """
    from apps.datasets.models import DatasetUpload
    from apps.peligros.models import ClasificacionPeligro

    importar()
    antes = ClasificacionPeligro.objects.count()
    assert antes > 0

    roto = tmp_path / "roto.xlsx"
    wb = openpyxl.load_workbook(MUESTRA_NIVEL)
    wb["Sismo"].cell(row=1, column=4).value = "COD"  # se esperaba CODIGO
    wb.save(roto)

    fallido = importar(archivo=roto)

    assert fallido.estado == DatasetUpload.Estado.ERROR
    assert "columnas inesperadas" in fallido.log["error"]
    assert ClasificacionPeligro.objects.count() == antes


def test_un_archivo_sin_hojas_conocidas_falla_con_mensaje_util(importar, tmp_path):
    from apps.datasets.models import DatasetUpload

    ajeno = tmp_path / "ajeno.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "Hoja1"
    wb.save(ajeno)

    upload = importar(archivo=ajeno)

    assert upload.estado == DatasetUpload.Estado.ERROR
    assert "ninguna de las 9 hojas esperadas" in upload.log["error"]


def test_reimportar_reemplaza_en_vez_de_duplicar(importar):
    """Dos importaciones del mismo archivo dan los mismos conteos, y la anterior queda marcada."""
    from apps.datasets.models import DatasetUpload
    from apps.peligros.models import ClasificacionPeligro

    primera = importar()
    conteo = ClasificacionPeligro.objects.count()

    segunda = importar()
    primera.refresh_from_db()

    assert ClasificacionPeligro.objects.count() == conteo
    assert primera.estado == DatasetUpload.Estado.REEMPLAZADO
    assert segunda.reemplaza_a_id == primera.pk
    assert not ClasificacionPeligro.objects.filter(dataset_upload=primera).exists()


def test_el_padron_no_se_borra_al_reimportar(importar):
    """Los centros poblados son el padrón: medidas y frecuencias los referencian.

    Las clasificaciones se reemplazan; los centros poblados se actualizan en su sitio.
    """
    from apps.territorio.models import CentroPoblado

    importar()
    pks = set(CentroPoblado.objects.values_list("pk", flat=True))

    importar()

    assert set(CentroPoblado.objects.values_list("pk", flat=True)) == pks


def test_frecuencia_sin_la_hoja_esperada_falla_citandola(importar, tmp_path):
    from apps.datasets.models import DatasetUpload

    sin_hoja = tmp_path / "sin_hoja.xlsx"
    wb = openpyxl.load_workbook(MUESTRA_FRECUENCIA)
    wb["NºEMERGENCIAS"].title = "Datos"
    wb.save(sin_hoja)

    upload = importar(tipo=DatasetUpload.Tipo.FRECUENCIA, archivo=sin_hoja)

    assert upload.estado == DatasetUpload.Estado.ERROR
    assert "NºEMERGENCIAS" in upload.log["error"]


def test_inversion_no_tiene_importador_todavia(importar):
    """ADR-D3: la opción existe para no migrar cuando llegue la data, el importador no.

    El mensaje tiene que ser explícito: un `error` mudo aquí se lee como una avería.
    """
    from apps.datasets.models import DatasetUpload

    upload = importar(tipo=DatasetUpload.Tipo.INVERSION, archivo=MUESTRA_FRECUENCIA)

    assert upload.estado == DatasetUpload.Estado.ERROR
    assert "importador" in upload.log["error"]
