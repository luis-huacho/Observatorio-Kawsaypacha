"""Cómo se colorea el coroplético del PP 0068 (ADR-D6).

Vive aparte porque lo leen **dos** consumidores que sin esto habrían tenido cada uno su copia:
la página que captura el navegador (`templates/informes/mapa_inversion.html`, vía su vista) y la
leyenda del reporte en PDF. Una rampa que se desincroniza entre el mapa y su propia leyenda es
un documento que miente sin que nada falle.

Queda una tercera copia inevitable en `frontend/src/components/MapaInversion.tsx`: es la misma
duplicación frontend/backend que ya tiene el semáforo de peligros, y traerla del API costaría
una petición para pintar cuatro colores.
"""

#: Blanco, no gris claro: con gris era indistinguible del tramo más bajo de la rampa, que es
#: justo la diferencia que el mapa existe para enseñar («no hay municipalidad» ≠ «hay poco»).
SIN_MUNICIPALIDAD = "#FFFFFF"
#: Hay municipalidad, pero con PIM cero no hay avance que calcular.
NO_CALCULABLE = "#DCDCD8"

#: Cinco tramos de la paleta (sky → mountain) para PIA, PIM y devengado.
RAMPA_DINERO = ["#D8EDF0", "#A8D8DF", "#5FBAC5", "#0095A4", "#00606B"]

#: El % de ejecución usa el semáforo del sitio y **cortes fijos**, no quintiles: es un
#: porcentaje, y con una escala relativa el mismo 90 % se pintaría de verde o de rojo según con
#: quién le tocara compartir la vista.
RAMPA_EJECUCION = ["#970A00", "#F57C15", "#EBB320", "#5BBB5D", "#009257"]
CORTES_EJECUCION = [0.25, 0.5, 0.75, 0.9]

METRICAS = {
    "pia": "PIA",
    "pim": "PIM",
    "devengado": "Devengado",
    "pct_ejecucion": "% de ejecución",
}
METRICA_POR_DEFECTO = "pim"


def metrica_valida(valor: str) -> str:
    return valor if valor in METRICAS else METRICA_POR_DEFECTO


def escala(metrica: str, cortes_por_metrica: dict) -> tuple[list, list]:
    """`(cortes, rampa)` de la métrica pedida.

    Los cortes de dinero **no se calculan aquí**: son los quintiles que ya vienen del API, para
    que el mapa y su leyenda usen exactamente los mismos.
    """
    metrica = metrica_valida(metrica)
    if metrica == "pct_ejecucion":
        return list(CORTES_EJECUCION), list(RAMPA_EJECUCION)
    return list(cortes_por_metrica.get(metrica) or [0, 0, 0, 0]), list(RAMPA_DINERO)
