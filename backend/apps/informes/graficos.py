"""Gráficos en SVG para los informes en PDF.

**WeasyPrint no ejecuta JavaScript**, así que los gráficos de Recharts que dibuja la pantalla no
se pueden reutilizar. Se generan aquí, en SVG, y eso resulta ser mejor que capturarlos con un
navegador por tres razones concretas:

- Es **vectorial**: nítido a cualquier zoom y al imprimir, donde un PNG se ve pastoso.
- Es **determinista**: no depende de Chromium ni de fuentes del sistema, así que se prueba con
  `assert` sobre la propia cadena.
- Mantiene el PDF **sin imágenes rasterizadas** salvo el mapa, que es lo que permite comprobar
  si el mapa llegó contando `/Subtype /Image` (ver `tests/test_informes.py`).

El SVG es a propósito pobre —`rect`, `line`, `polyline`, `text`—: el soporte de WeasyPrint no
cubre filtros, gradientes ni CSS avanzado dentro del SVG, y un gráfico que no se dibuja es peor
que uno feo.

Los colores no se deciden aquí: se pasan desde fuera, para que el documento y la pantalla usen
los mismos (los de la paleta en `tailwind.config.ts`, y los de los procesos, los de la base).
"""
from html import escape

#: Rejilla y ejes. Gris claro, para que no compitan con los datos.
COLOR_EJE = "#D1D5DB"
COLOR_TEXTO = "#6B7280"


def _n(valor) -> float:
    """Número utilizable. Un `None` en una serie es un cero a efectos de dibujo, no un hueco."""
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def _millones(valor: float) -> str:
    """Etiqueta corta de importe. En un gráfico de papel no cabe «S/ 54,591,255»."""
    v = _n(valor)
    if abs(v) >= 1_000_000:
        return f"S/ {v / 1_000_000:,.1f}M"
    if abs(v) >= 1_000:
        return f"S/ {v / 1_000:,.0f}k"
    return f"S/ {v:,.0f}"


def _escala(maximo: float) -> float:
    """Denominador seguro.

    Con todos los valores a cero —una provincia sin presupuesto, un proceso vacío— dividir por el
    máximo daría `ZeroDivisionError` o barras de altura infinita. Devolver 1 dibuja el gráfico
    plano, que es exactamente lo que pasa.
    """
    return maximo if maximo > 0 else 1.0


def barras_verticales(items, ancho: int = 470, alto: int = 200) -> str:
    """Barras verticales con su importe encima. Alimenta PIA → PIM → devengado.

    `items` es una secuencia de `(etiqueta, valor, color)`.
    """
    items = list(items)
    if not items:
        return _vacio(ancho, alto)

    margen_inf, margen_sup = 30, 22
    util = alto - margen_inf - margen_sup
    paso = ancho / len(items)
    grosor = min(paso * 0.5, 70)
    maximo = _escala(max(_n(v) for _, v, _ in items))

    piezas = [f'<line x1="0" y1="{alto - margen_inf}" x2="{ancho}" y2="{alto - margen_inf}" '
              f'stroke="{COLOR_EJE}" stroke-width="1"/>']
    for i, (etiqueta, valor, color) in enumerate(items):
        altura = util * _n(valor) / maximo
        x = paso * i + (paso - grosor) / 2
        y = alto - margen_inf - altura
        piezas.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{grosor:.1f}" height="{altura:.1f}" '
            f'fill="{color}"/>'
        )
        piezas.append(
            f'<text x="{paso * i + paso / 2:.1f}" y="{y - 5:.1f}" text-anchor="middle" '
            f'font-size="9" fill="{COLOR_TEXTO}">{escape(_millones(valor))}</text>'
        )
        piezas.append(
            f'<text x="{paso * i + paso / 2:.1f}" y="{alto - margen_inf + 13}" '
            f'text-anchor="middle" font-size="9" fill="#1F2937">{escape(str(etiqueta))}</text>'
        )
    return _envolver(piezas, ancho, alto)


def barras_horizontales(items, ancho: int = 470, alto_fila: int = 20, ancho_etiqueta: int = 130) -> str:
    """Barras horizontales con etiqueta a la izquierda. Alimenta los procesos de la GRD.

    Horizontal y no vertical por el mismo motivo que en pantalla: «Prevención y reducción» o
    «Gestión transversal» no caben bajo una barra vertical sin girar el texto.
    """
    items = list(items)
    if not items:
        return _vacio(ancho, alto_fila * 2)

    alto = alto_fila * len(items) + 6
    disponible = ancho - ancho_etiqueta - 60
    maximo = _escala(max(_n(v) for _, v, _ in items))

    piezas = []
    for i, (etiqueta, valor, color) in enumerate(items):
        y = alto_fila * i + 3
        largo = disponible * _n(valor) / maximo
        piezas.append(
            f'<text x="{ancho_etiqueta - 6}" y="{y + alto_fila * 0.62:.1f}" text-anchor="end" '
            f'font-size="8.5" fill="#1F2937">{escape(str(etiqueta))}</text>'
        )
        piezas.append(
            f'<rect x="{ancho_etiqueta}" y="{y:.1f}" width="{max(largo, 0.5):.1f}" '
            f'height="{alto_fila * 0.66:.1f}" fill="{color}"/>'
        )
        piezas.append(
            f'<text x="{ancho_etiqueta + largo + 5:.1f}" y="{y + alto_fila * 0.55:.1f}" '
            f'font-size="8" fill="{COLOR_TEXTO}">{escape(_millones(valor))}</text>'
        )
    return _envolver(piezas, ancho, alto)


def barra_apilada(segmentos, ancho: int = 470, alto: int = 16) -> str:
    """Una barra de varios tramos, proporcional al total. Alimenta proyectos vs actividades.

    Con el total a cero devuelve el hueco vacío en vez de una barra: no hay reparto que enseñar.
    """
    segmentos = [(e, _n(v), c) for e, v, c in segmentos]
    total = sum(v for _, v, _ in segmentos)
    if total <= 0:
        return _vacio(ancho, alto)

    piezas, x = [], 0.0
    for _, valor, color in segmentos:
        w = ancho * valor / total
        piezas.append(f'<rect x="{x:.1f}" y="0" width="{w:.1f}" height="{alto}" fill="{color}"/>')
        x += w
    return _envolver(piezas, ancho, alto)


def lineas(etiquetas, series, ancho: int = 470, alto: int = 190) -> str:
    """Varias series sobre el mismo eje. Alimenta la tendencia 2022-2026.

    `series` es una secuencia de `(nombre, valores, color, punteada)`. El PIA va punteado igual
    que en pantalla: es el punto de partida, y la distancia hasta el PIM *es* la variación.
    """
    etiquetas = list(etiquetas)
    series = list(series)
    if len(etiquetas) < 2 or not series:
        return _vacio(ancho, alto)

    izq, margen_inf, margen_sup = 46, 26, 10
    util_x, util_y = ancho - izq - 8, alto - margen_inf - margen_sup
    maximo = _escala(max((_n(v) for _, vals, _, _ in series for v in vals), default=0))
    paso = util_x / (len(etiquetas) - 1)

    piezas = []
    # Tres líneas de rejilla con su valor: sin ellas, dos series de magnitudes parecidas no se
    # pueden leer, y en papel no hay tooltip al que recurrir.
    for k in range(4):
        y = margen_sup + util_y * k / 3
        piezas.append(f'<line x1="{izq}" y1="{y:.1f}" x2="{ancho - 8}" y2="{y:.1f}" '
                      f'stroke="{COLOR_EJE}" stroke-width="0.5" stroke-dasharray="3 3"/>')
        piezas.append(f'<text x="{izq - 5}" y="{y + 3:.1f}" text-anchor="end" font-size="7.5" '
                      f'fill="{COLOR_TEXTO}">{escape(_millones(maximo * (3 - k) / 3))}</text>')

    for i, etiqueta in enumerate(etiquetas):
        piezas.append(
            f'<text x="{izq + paso * i:.1f}" y="{alto - margen_inf + 13}" text-anchor="middle" '
            f'font-size="8" fill="#1F2937">{escape(str(etiqueta))}</text>'
        )

    for _, valores, color, punteada in series:
        puntos = " ".join(
            f"{izq + paso * i:.1f},{margen_sup + util_y - util_y * _n(v) / maximo:.1f}"
            for i, v in enumerate(valores[: len(etiquetas)])
        )
        trazo = ' stroke-dasharray="5 4"' if punteada else ""
        piezas.append(
            f'<polyline points="{puntos}" fill="none" stroke="{color}" stroke-width="1.8"'
            f'{trazo} stroke-linejoin="round"/>'
        )
        for i, v in enumerate(valores[: len(etiquetas)]):
            piezas.append(
                f'<circle cx="{izq + paso * i:.1f}" '
                f'cy="{margen_sup + util_y - util_y * _n(v) / maximo:.1f}" r="2" fill="{color}"/>'
            )
    return _envolver(piezas, ancho, alto)


def _envolver(piezas, ancho, alto) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto:.0f}" '
        f'viewBox="0 0 {ancho} {alto:.0f}" font-family="sans-serif">'
        + "".join(piezas)
        + "</svg>"
    )


def _vacio(ancho, alto) -> str:
    """Un SVG con la nota, no una cadena vacía.

    Devolver "" dejaría un hueco mudo en el documento y el lector no sabría si el gráfico falta
    porque no hay datos o porque algo se rompió.
    """
    return _envolver(
        [f'<text x="{ancho / 2}" y="{alto / 2}" text-anchor="middle" font-size="9" '
         f'fill="{COLOR_TEXTO}">Sin datos para este gráfico</text>'],
        ancho,
        alto,
    )
