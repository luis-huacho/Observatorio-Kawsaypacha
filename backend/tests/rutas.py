"""Rutas de los archivos de datos que usan las pruebas.

En un módulo aparte para que `conftest.py` y las pruebas marcadas `lento` compartan la misma
definición y no haya dos ideas de dónde vive cada archivo.
"""
import pathlib

from django.conf import settings

AQUI = pathlib.Path(__file__).resolve().parent

#: Muestras reducidas, versionadas. Cada anomalía verificada en la auditoría está representada;
#: ver `tests/datos/generar_muestras.py` para el detalle de qué contiene cada una.
MUESTRA_NIVEL = AQUI / "datos" / "nivel_peligro_muestra.xlsx"
MUESTRA_FRECUENCIA = AQUI / "datos" / "frecuencia_muestra.xlsx"
#: Las dos series de inversión, en CSV como salen de `scripts/`. Se escriben a mano y no se
#: generan: cada fila representa un caso —proyecto, actividad conocida, código desconocido,
#: municipalidad fuera del padrón, gobierno regional— y hay que poder leerlas.
MUESTRA_INVERSION = AQUI / "datos" / "inversion_serie_muestra.csv"
MUESTRA_INVERSION_INSTITUCIONAL = AQUI / "datos" / "inversion_institucional_muestra.csv"

#: Los Excel completos (5.4 MB), que **no** se versionan. Solo las pruebas `lento` los usan, y
#: se saltan solas cuando no están.
REALES = pathlib.Path(settings.DATOS_FUENTE_DIR) / "data"
REAL_NIVEL = REALES / "Base_Nivel Peligro_CCPP_Cusco.xlsx"
REAL_FRECUENCIA = REALES / "Base_Frecuencia_Peligro_Cusco.xlsx"


def hay_datos_reales() -> bool:
    return REAL_NIVEL.exists() and REAL_FRECUENCIA.exists()
