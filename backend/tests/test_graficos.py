"""Gráficos SVG de los informes.

No tocan la base de datos ni el navegador: son funciones puras, y eso es justamente lo que
permite fijar aquí los casos que en un gráfico se ven «raros» pero no fallan —una serie vacía,
todo a cero— y que en un PDF nadie revisa hasta que un documento sale mal en una reunión.
"""
import pytest

from apps.informes import graficos


def test_una_serie_vacia_dice_que_no_hay_datos_en_vez_de_desaparecer():
    """Un hueco mudo no distingue «no hay datos» de «el gráfico se rompió»."""
    for svg in (
        graficos.barras_verticales([]),
        graficos.barras_horizontales([]),
        graficos.barra_apilada([]),
        graficos.lineas([], []),
    ):
        assert svg.startswith("<svg")
        assert "Sin datos" in svg


@pytest.mark.parametrize(
    "dibujar",
    [
        lambda: graficos.barras_verticales([("PIA", 0, "#000"), ("PIM", 0, "#111")]),
        lambda: graficos.barras_horizontales([("Preparación", 0, "#000")]),
        lambda: graficos.lineas(["2025", "2026"], [("PIM", [0, 0], "#000", False)]),
    ],
)
def test_todo_a_cero_no_revienta_ni_produce_barras_infinitas(dibujar):
    """El máximo es el denominador de la escala: con todo a cero sería una división por cero.

    El gráfico sale plano, que es exactamente lo que dicen los datos.
    """
    svg = dibujar()

    assert svg.startswith("<svg")
    assert "inf" not in svg.lower() and "nan" not in svg.lower()


def test_la_barra_apilada_reparte_el_ancho_en_proporcion():
    svg = graficos.barra_apilada(
        [("Proyectos", 25, "#007480"), ("Actividades", 75, "#F1DCC0")], ancho=400
    )

    # Un cuarto y tres cuartos del ancho, en ese orden.
    assert 'width="100.0"' in svg
    assert 'width="300.0"' in svg


def test_la_barra_apilada_sin_total_no_dibuja_un_reparto_falso():
    """Con cero soles no hay proporción que enseñar, y un 50/50 sería inventado."""
    svg = graficos.barra_apilada([("Proyectos", 0, "#007480"), ("Actividades", 0, "#F1DCC0")])

    assert "Sin datos" in svg


def test_los_importes_se_abrevian_para_que_quepan_en_papel():
    svg = graficos.barras_verticales([("PIM", 54_591_255, "#007480")])

    assert "S/ 54.6M" in svg
    assert "54,591,255" not in svg


def test_la_serie_punteada_se_distingue_de_la_continua():
    """El PIA va punteado como en pantalla; si las tres salieran iguales, el gráfico mentiría
    sobre cuál es el punto de partida y cuál el resultado."""
    svg = graficos.lineas(
        ["2025", "2026"],
        [("PIA", [1, 2], "#B8753C", True), ("PIM", [3, 4], "#007480", False)],
    )

    assert svg.count("stroke-dasharray") >= 1
    assert "#B8753C" in svg and "#007480" in svg


def test_las_etiquetas_se_escapan():
    """Los nombres vienen de la base y acaban dentro de un SVG que se inyecta con `safe`."""
    svg = graficos.barras_horizontales([("Preparación & <respuesta>", 10, "#000")])

    assert "&amp;" in svg and "&lt;respuesta&gt;" in svg
    assert "<respuesta>" not in svg
