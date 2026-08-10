"""Ventana Inversión (PP 0068) — contrato del API y derivados.

Los derivados son el punto delicado: saldo, variación PIA-PIM, % de ejecución y % sobre el
institucional se ven bien aunque estén mal, porque son números plausibles en cualquier caso.
Cada prueba de aquí fija uno contra cifras que se pueden comprobar a mano en
`tests/datos/inversion_serie_muestra.csv`.
"""
import pytest

from tests.rutas import MUESTRA_INVERSION, MUESTRA_INVERSION_INSTITUCIONAL

pytestmark = pytest.mark.django_db


@pytest.fixture
def inversion_cargada(importar, datos_muestra):
    """Las dos series importadas y los ejercicios publicados."""
    from apps.datasets.models import DatasetUpload
    from apps.inversion.models import Ejercicio

    importar(tipo=DatasetUpload.Tipo.INVERSION, archivo=MUESTRA_INVERSION)
    importar(tipo=DatasetUpload.Tipo.INVERSION, archivo=MUESTRA_INVERSION_INSTITUCIONAL)
    Ejercicio.objects.update(visible=True)
    return Ejercicio.objects.get(anio=2026)


def test_sin_ejercicio_visible_responde_el_contrato_de_sin_datos(api, inversion_cargada):
    """Ocultar los ejercicios devuelve la ventana a su estado vacío, sin romper el cliente.

    Es el mismo contrato que servía la ventana cuando estaba diferida (ADR-D3): el frontend no
    necesita un caso especial para «hay datos pero no publicados».
    """
    from apps.inversion.models import Ejercicio

    Ejercicio.objects.update(visible=False)

    cuerpo = api.get("/api/inversion/").json()

    assert cuerpo["disponible"] is False
    assert cuerpo["motivo"]
    assert "por_entidad" not in cuerpo


def test_un_anio_oculto_no_cae_al_ultimo_visible(api, inversion_cargada):
    """Pedir un ejercicio que no se publica devuelve vacío, no el de otro año.

    Servir 2026 cuando piden 2025 se vería perfecto y todas las cifras serían del año
    equivocado, que es peor que no mostrar nada.
    """
    from apps.inversion.models import Ejercicio

    Ejercicio.objects.filter(anio=2025).update(visible=False)

    assert api.get("/api/inversion/?anio=2025").json()["disponible"] is False
    assert api.get("/api/inversion/?anio=2026").json()["anio"] == 2026


def test_por_defecto_sirve_el_ejercicio_mas_reciente(api, inversion_cargada):
    cuerpo = api.get("/api/inversion/").json()

    assert cuerpo["disponible"] is True
    assert cuerpo["anio"] == 2026
    assert cuerpo["ambito"] == "municipal"


def test_declara_el_corte_parcial_y_la_fuente(api, inversion_cargada):
    """Un % de ejecución de medio año no es comparable con uno de año cerrado, y el payload
    tiene que decirlo: la advertencia no puede depender de que la interfaz se acuerde."""
    cuerpo = api.get("/api/inversion/?anio=2026").json()

    assert cuerpo["es_parcial"] is True
    assert cuerpo["corte"] == "2026-06"
    assert "PREDES" in cuerpo["fuente"]

    cerrado = api.get("/api/inversion/?anio=2025").json()
    assert cerrado["es_parcial"] is False

    # La tendencia arrastra la marca punto a punto: la serie mezcla dos fuentes.
    assert [(p["anio"], p["es_parcial"]) for p in cuerpo["tendencia"]] == [
        (2025, False),
        (2026, True),
    ]


def test_los_derivados_de_una_entidad_cuadran_a_mano(api, inversion_cargada):
    """Cusco 2026: PIA 100 000, PIM 220 000, devengado 65 000, institucional 2 200 000."""
    cuerpo = api.get("/api/inversion/?anio=2026").json()
    cusco = next(f for f in cuerpo["por_entidad"] if f["codigo"] == "300684")

    assert cusco["pia"] == 100_000
    assert cusco["pim"] == 220_000
    assert cusco["devengado"] == 65_000
    assert cusco["pct_ejecucion"] == pytest.approx(65_000 / 220_000)
    assert cusco["saldo"] == 155_000
    assert cusco["variacion_pia_pim"] == 120_000
    assert cusco["pct_0068_institucional"] == pytest.approx(220_000 / 2_200_000)
    # Cusco solo tiene actividades en 2026; Poroy es quien aporta el proyecto.
    assert cusco["pct_proyectos"] == 0


def test_sin_total_institucional_el_porcentaje_es_nulo_y_no_cero(api, inversion_cargada):
    """`None` y `0` se dibujan distinto, y una municipalidad sin denominador no tiene un 0 %.

    Poroy no trae fila institucional de 2026 en la muestra: su porcentaje no se puede calcular.
    """
    cuerpo = api.get("/api/inversion/?anio=2026").json()
    poroy = next(f for f in cuerpo["por_entidad"] if f["codigo"] == "300686")

    assert poroy["pim_institucional"] is None
    assert poroy["pct_0068_institucional"] is None


def test_el_porcentaje_agregado_solo_usa_entidades_comparables(api, inversion_cargada):
    """El % del 0068 sobre el institucional no puede mezclar numerador y denominador.

    Si el numerador sumara las dos municipalidades y el denominador solo la que tiene total,
    saldría inflado sin que nada lo dijera. Solo entra Cusco: 220 000 / 2 200 000.
    """
    agregados = api.get("/api/inversion/?anio=2026").json()["agregados"]

    assert agregados["entidades_con_institucional"] == 1
    assert agregados["pct_0068_institucional"] == pytest.approx(220_000 / 2_200_000)


def test_el_ambito_municipal_deja_fuera_al_gobierno_regional(api, inversion_cargada):
    """El GORE tiene 900 000 en la muestra: colarlo en el ranking municipal lo dominaría."""
    municipal = api.get("/api/inversion/?anio=2026").json()
    codigos = {f["codigo"] for f in municipal["por_entidad"]}

    assert "446" not in codigos
    assert municipal["agregados"]["pim"] == 535_000  # 220 000 + 310 000 + 5 000

    regional = api.get("/api/inversion/?anio=2026&ambito=regional").json()
    assert {f["codigo"] for f in regional["por_entidad"]} == {"446"}


def test_el_reparto_por_procesos_sale_del_catalogo_vigente(api, inversion_cargada):
    """Editar el catálogo cambia el gráfico sin volver a importar ni recalcular nada."""
    from apps.inversion.models import ClasificacionActividad, ProcesoGRD

    antes = {p["slug"]: p["pim"] for p in api.get("/api/inversion/?anio=2026").json()["procesos"]}
    assert antes["preparacion"] == 200_000
    assert antes["estimacion"] == 20_000

    ClasificacionActividad.objects.filter(codigo="5005561").update(
        proceso=ProcesoGRD.objects.get(slug="respuesta"), automatico=False
    )

    despues = {p["slug"]: p["pim"] for p in api.get("/api/inversion/?anio=2026").json()["procesos"]}
    assert despues["preparacion"] == 0
    assert despues["respuesta"] == 200_000


def test_lo_que_el_catalogo_no_clasifica_se_declara_aparte(api, inversion_cargada):
    """El código desconocido de la muestra (5009999, 10 000) no se reparte ni desaparece."""
    cuerpo = api.get("/api/inversion/?anio=2026").json()

    assert cuerpo["sin_clasificar"]["pim"] == 10_000
    assert sum(p["pim"] for p in cuerpo["procesos"]) + cuerpo["sin_clasificar"]["pim"] == (
        cuerpo["agregados"]["pim"]
    )


def test_filtra_por_provincia(api, inversion_cargada):
    cuerpo = api.get("/api/inversion/?anio=2026&provincia=CUSCO").json()

    assert {f["provincia"] for f in cuerpo["por_entidad"]} == {"CUSCO"}
    assert api.get("/api/inversion/?anio=2026&provincia=9999").json()["por_entidad"] == []


def test_el_export_lleva_el_corte_en_cada_fila(api, inversion_cargada, sin_throttling):
    """El Excel viaja suelto por correo: sin el corte, un 30 % de ejecución parece de un año."""
    import io

    import openpyxl

    respuesta = api.get("/api/inversion/export.xlsx?anio=2026")

    assert respuesta.status_code == 200
    hoja = openpyxl.load_workbook(io.BytesIO(respuesta.content)).active
    filas = list(hoja.iter_rows(values_only=True))
    assert filas[0][:3] == ("Ejercicio", "Corte", "Fuente")
    assert all(f[1] == "2026-06" for f in filas[1:])


def test_el_export_sin_datos_explica_por_que(api, inversion_cargada, sin_throttling):
    """Un Excel vacío se abre igual y parece que no hay presupuesto."""
    import io

    import openpyxl

    from apps.inversion.models import Ejercicio

    Ejercicio.objects.update(visible=False)
    respuesta = api.get("/api/inversion/export.xlsx")

    hoja = openpyxl.load_workbook(io.BytesIO(respuesta.content)).active
    assert [c.value for c in hoja[1]] == ["Motivo"]
    assert "PREDES" in hoja.cell(row=2, column=1).value
