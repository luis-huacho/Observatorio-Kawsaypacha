"""Las frases que van bajo cada gráfico de Inversión.

Se prueban aquí y no por el texto renderizado porque son la **única** redacción: la pantalla y
el PDF imprimen esto mismo, así que un fallo de redacción sale en los dos sitios a la vez.
"""
import pytest

from apps.inversion import declaraciones


def _agregados(**extra):
    base = {
        "pia": 1_000_000, "pim": 5_000_000, "devengado": 2_000_000,
        "pct_ejecucion": 0.4, "saldo": 3_000_000, "variacion_pia_pim": 4_000_000,
    }
    return {**base, **extra}


def _anio(anio, pim, devengado, parcial=False, corte_legible=""):
    return {
        "anio": anio, "pim": pim, "devengado": devengado, "pia": 0,
        "es_parcial": parcial, "corte_legible": corte_legible,
    }


# --- Formato ---------------------------------------------------------------


@pytest.mark.parametrize(
    "valor,esperado",
    [(0.53, "53%"), (0.9765, "97.7%"), (12.727, "1,272.7%"), (0, "0%"), (0.007995, "0.8%")],
)
def test_el_porcentaje_web_es_el_mismo_que_pinta_el_navegador(valor, esperado):
    """`Intl` con `maximumFractionDigits: 1`: sin espacio, sin `.0` y con separador de millar.

    La cadena viaja hecha desde el servidor, así que si aquí se escribiera de otra forma la
    frase desentonaría con los KPI de al lado, que sí los formatea el navegador.
    """
    assert declaraciones.pct_web(valor) == esperado


# --- Ejecución -------------------------------------------------------------


def test_la_ejecucion_declara_la_variacion_y_el_saldo():
    frase = declaraciones.ejecucion(_agregados(), corte="junio")
    assert "El presupuesto creció S/ 4,000,000 (400%)" in frase
    assert "Al corte de junio se ha devengado el 40% y quedan S/ 3,000,000 por ejecutar." in frase


def test_sin_corte_la_ejecucion_no_inventa_uno():
    """Un ejercicio completo no lleva «al corte de»: no hay corte que nombrar."""
    frase = declaraciones.ejecucion(_agregados(), corte="")
    assert "Se ha devengado el 40%" in frase
    assert "corte" not in frase


def test_un_presupuesto_que_baja_no_dice_que_creció():
    frase = declaraciones.ejecucion(
        _agregados(pia=5_000_000, pim=4_000_000, variacion_pia_pim=-1_000_000)
    )
    assert "se redujo en S/ 1,000,000 (20%)" in frase
    assert "creció" not in frase


def test_sin_pim_no_hay_nada_que_declarar():
    """Un ámbito sin presupuesto no deja un filete con una frase vacía debajo del gráfico."""
    assert declaraciones.ejecucion(_agregados(pim=0)) is None


# --- Procesos --------------------------------------------------------------


def test_los_procesos_declaran_dónde_se_concentra_y_qué_está_en_cero():
    lista = [
        {"nombre": "Estimación del riesgo", "pim": 100, "pct": 0.1},
        {"nombre": "Prevención y reducción", "pim": 900, "pct": 0.9},
        {"nombre": "Rehabilitación", "pim": 0, "pct": 0.0},
    ]
    frase = declaraciones.procesos(lista, {"pim": 0})
    assert "Prevención y reducción concentra el 90% del presupuesto vigente (S/ 900)." in frase
    # Un proceso en cero es un hallazgo, no un hueco: la barra vacía no se explica sola.
    assert "Rehabilitación no tiene presupuesto en este ejercicio." in frase


def test_los_procesos_declaran_lo_que_el_catalogo_no_imputa():
    lista = [{"nombre": "Respuesta", "pim": 900, "pct": 0.9}]
    frase = declaraciones.procesos(lista, {"pim": 100, "pct": 0.1})
    assert "S/ 100 cuelgan de códigos que el catálogo aún no imputa" in frase


def test_dos_procesos_en_cero_se_enumeran_en_castellano():
    lista = [
        {"nombre": "Respuesta", "pim": 900, "pct": 1.0},
        {"nombre": "Rehabilitación", "pim": 0, "pct": 0.0},
        {"nombre": "Preparación", "pim": 0, "pct": 0.0},
    ]
    assert "Rehabilitación y Preparación no tienen presupuesto" in declaraciones.procesos(
        lista, {"pim": 0}
    )


# --- Tendencia -------------------------------------------------------------


def test_la_tendencia_compara_los_dos_ultimos_ejercicios_completos():
    """Y NO el corte parcial contra el año entero, que mediría medio año contra doce meses."""
    serie = [
        _anio(2024, 1_000_000, 800_000),
        _anio(2025, 1_500_000, 1_200_000),
        _anio(2026, 900_000, 300_000, parcial=True, corte_legible="junio de 2026"),
    ]
    frase = declaraciones.tendencia(serie)

    assert "Entre 2024 y 2025, los dos últimos ejercicios completos" in frase
    assert "el presupuesto vigente subió S/ 500,000 (50%)" in frase
    assert "el gasto ejecutado subió S/ 400,000 (50%)" in frase
    # El parcial se nombra, nunca se compara: no hay variación colgada de 2026.
    assert "El ejercicio 2026 va al corte de junio y no se compara con ellos." in frase
    assert "bajó" not in frase


def test_la_tendencia_no_dice_cerrado():
    """Jerga contable, y hay una prueba e2e que fija que no aparece en la interfaz."""
    serie = [_anio(2024, 1_000_000, 800_000), _anio(2025, 900_000, 700_000)]
    assert "cerrado" not in declaraciones.tendencia(serie).lower()


def test_con_un_solo_ejercicio_completo_no_se_inventa_una_comparacion():
    serie = [_anio(2026, 900_000, 300_000, parcial=True, corte_legible="junio de 2026")]
    frase = declaraciones.tendencia(serie)
    assert "los dos últimos" not in frase
    assert "El ejercicio 2026 va al corte de junio" in frase


# --- Proyectos -------------------------------------------------------------


def _bloque(*importes):
    entidades = [
        {"codigo": f"3007{i:02d}", "entidad": f"MUNICIPALIDAD {i}", "pim_proyectos": importe}
        for i, importe in enumerate(importes)
    ]
    return {"pim": sum(importes), "con_proyectos": len(importes), "de": 116,
            "entidades": entidades}


def test_los_proyectos_declaran_cuantas_son_y_la_concentracion():
    frase = declaraciones.proyectos(_bloque(700, 200, 20, 20, 20, 20, 20))
    assert "7 de las 116 municipalidades del ámbito tienen presupuesto en proyectos" in frase
    assert "Las 2 primeras concentran el 90% (S/ 900)." in frase
    # La lectura equivocada que este bloque existe para corregir.
    assert "El Gobierno Regional no entra en este ámbito" in frase


def test_con_una_sola_concentrando_se_la_nombra_en_vez_de_contarla():
    """«Las 1 primeras» no es castellano, y saber CUÁL se lleva el dinero es lo que se busca."""
    frase = declaraciones.proyectos(_bloque(900, 50, 50))
    assert "MUNICIPALIDAD 0 concentra el 90% (S/ 900)." in frase
    assert "Las 1 primeras" not in frase


def test_sin_ninguna_municipalidad_con_obra_se_dice_asi():
    bloque = {"pim": 0, "con_proyectos": 0, "de": 116, "entidades": []}
    assert "Ninguna municipalidad" in declaraciones.proyectos(bloque)


def test_si_el_reparto_es_plano_no_se_declara_una_concentracion_falsa():
    """Con cinco iguales, cuatro suman el 80 % por aritmética, no por concentración.

    Decirlo haría sonar concentrado lo que está repartido, que es lo contrario de lo que la
    frase viene a contar — y no fallaría a la vista: la cifra sería correcta y la lectura,
    falsa. Solo se declara cuando las que se llevan el 80 % son una minoría.
    """
    frase = declaraciones.proyectos(_bloque(*([100] * 5)))
    assert "concentran" not in frase
    assert "5 de las 116" in frase


# --- La distribución del mapa ----------------------------------------------


def _dist(**extra):
    base = {
        "n": 99, "ceros": 1, "q1": 38_000.0, "mediana": 73_510.0, "q3": 179_422.0,
        "bigote_min": 2_300.0, "bigote_max": 370_009.0,
        "atipicos": [{"nombre": "PICHARI", "valor": 9_331_232.0}],
    }
    return {**base, **extra}


def test_la_frase_del_mapa_dice_donde_esta_la_mitad_y_quien_se_sale():
    """El coroplético no puede enseñar el reparto: su último tramo se come toda la cola.

    Con la mediana en S/ 73.510 y PICHARI en 9,3 M —127 veces— un distrito de 220 mil y otro de
    nueve millones salen del mismo color. La frase es lo que dice en palabras lo que el color
    aplana, así que tiene que traer el rango central, cuántos se salen y el mayor con su nombre.
    """
    frase = declaraciones.distribucion(_dist(), "pim", "distrital")

    assert "S/ 38,000" in frase and "S/ 179,422" in frase
    assert "99 distritos" in frase
    assert "PICHARI" in frase and "S/ 9,331,232" in frase


def test_sin_atipicos_la_frase_no_inventa_ninguno():
    """El % de ejecución no tiene cola: 98 distritos entre 0 y 100 % y ni un valor fuera de rango.

    Una frase que dijera «0 quedan fuera» sería ruido; la que se calla es la correcta.
    """
    frase = declaraciones.distribucion(
        _dist(n=98, ceros=0, q1=0.267, mediana=0.469, q3=0.705, atipicos=[]),
        "pct_ejecucion",
        "distrital",
    )

    assert "26.7%" in frase and "70.5%" in frase
    assert "fuera" not in frase
    # Y el porcentaje no se escribe en soles, que es el fallo que no rompe nada.
    assert "S/" not in frase


def test_los_ceros_se_cuentan_en_la_frase_porque_no_caben_en_la_escala():
    """Nueve distritos con devengado 0 no se pueden dibujar en un eje logarítmico.

    Excluirlos del dibujo está bien; excluirlos **sin decirlo** deja una caja calculada sobre 99
    valores encima de un gráfico que enseña 90, sin que nada falle.

    Y se dicen «con S/ 0», no «sin presupuesto»: en el devengado eso sería falso —un distrito
    puede tener PIM y no haber gastado un sol— y es el tipo de frase que se lee como un dato.
    """
    frase = declaraciones.distribucion(_dist(ceros=9), "devengado", "distrital")

    assert "9 distritos con S/ 0" in frase
    assert "sin presupuesto" not in frase


def test_el_porcentaje_no_habla_de_la_escala_porque_el_cero_si_cabe():
    """El % de ejecución se dibuja en una escala lineal de 0 a 100: un 0 % es un punto válido.

    Arrastrar aquí la advertencia del eje logarítmico contaría una limitación que no existe.
    """
    frase = declaraciones.distribucion(
        _dist(ceros=8, q1=0.268, mediana=0.469, q3=0.705, atipicos=[]),
        "pct_ejecucion",
        "distrital",
    )

    assert "escala" not in frase
    assert "S/" not in frase


def test_la_frase_concuerda_en_genero_con_lo_que_cuenta():
    """«los 13 provincias» es el descuido que delata una frase generada por una máquina."""
    assert "las 13 provincias" in declaraciones.distribucion(_dist(n=13), "pim", "provincial")
    assert "los 99 distritos" in declaraciones.distribucion(_dist(), "pim", "distrital")


def test_una_distribucion_vacia_no_deja_una_frase_a_medias():
    """Un ámbito sin filas: mejor ninguna frase que «La mitad de los 0 distritos está entre…»."""
    assert declaraciones.distribucion(_dist(n=0), "pim", "distrital") is None


def test_a_nivel_provincial_la_frase_habla_de_provincias():
    frase = declaraciones.distribucion(_dist(n=13), "pim", "provincial")

    assert "las 13 provincias" in frase
    assert "distritos" not in frase
