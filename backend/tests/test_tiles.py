"""Emisión de los datos que alimentan los tiles (spec 05).

El pipeline completo —ogr2ogr, tippecanoe, el swap atómico— se comprueba a mano y en el arranque;
lo que se prueba aquí es **lo que se le entrega a tippecanoe**, porque una equivocación en las
claves de las propiedades no rompe nada visible: el tile se genera, pesa lo que debe, el visor lo
carga… y sale todo en gris.
"""
import json

import pytest

pytestmark = pytest.mark.django_db


def _features(destino):
    from apps.mapas.pipeline import escribir_geojsonseq_ccpp

    escritos = escribir_geojsonseq_ccpp(destino)
    lineas = destino.read_text(encoding="utf-8").splitlines()
    return escritos, [json.loads(linea) for linea in lineas]


def test_una_feature_por_centro_poblado_con_coordenadas(datos_muestra, tmp_path):
    from apps.territorio.models import CentroPoblado

    escritos, features = _features(tmp_path / "ccpp.geojsonseq")
    esperados = CentroPoblado.objects.exclude(lat=None).exclude(lon=None).count()

    assert escritos == esperados == len(features)
    assert all(f["geometry"]["type"] == "Point" for f in features)


def test_las_claves_de_nivel_ausentes_se_omiten_no_se_escriben_como_nulas(
    datos_muestra, tmp_path
):
    """Es lo que mantiene el tile en 3 MB y «sin dato» como categoría propia.

    Con `null` en cada peligro no evaluado, cada punto cargaría 9 propiedades vacías —los 5,730
    centros poblados sin clasificar del archivo real, sobre todo— y el visor no podría distinguir
    «no evaluado» de «nivel bajo» con una expresión de MapLibre.
    """
    _, features = _features(tmp_path / "ccpp.geojsonseq")
    sin_clasificar = [
        f for f in features if not any(k.startswith("nivel_") for k in f["properties"])
    ]

    assert sin_clasificar, "la muestra no dejó centros poblados sin clasificar"
    for feature in features:
        for clave, valor in feature["properties"].items():
            if clave.startswith("nivel_"):
                assert valor is not None
    assert all("nivel_max" not in f["properties"] for f in sin_clasificar)


def test_las_claves_emitidas_coinciden_con_los_slugs_del_catalogo(datos_muestra, tmp_path):
    """`nivel_<slug>` es el contrato entre el emisor y el visor.

    El slug lleva guion **bajo**: con guion medio el visor deja de pintar y ninguna otra prueba
    lo nota.
    """
    from apps.peligros.models import TipoPeligro

    _, features = _features(tmp_path / "ccpp.geojsonseq")
    emitidas = {
        clave
        for f in features
        for clave in f["properties"]
        if clave.startswith("nivel_") and clave != "nivel_max"
    }
    validas = {f"nivel_{s}" for s in TipoPeligro.objects.values_list("slug", flat=True)}

    assert emitidas
    assert emitidas <= validas
    assert not [c for c in emitidas if "-" in c]


def test_nivel_max_es_el_maximo_de_los_niveles_presentes(datos_muestra, tmp_path):
    """Es la propiedad con la que el visor decide el color de cada punto."""
    _, features = _features(tmp_path / "ccpp.geojsonseq")
    comprobados = 0

    for feature in features:
        niveles = [
            v for k, v in feature["properties"].items()
            if k.startswith("nivel_") and k != "nivel_max"
        ]
        if not niveles:
            continue
        assert feature["properties"]["nivel_max"] == max(niveles)
        comprobados += 1

    assert comprobados, "ninguna feature traía niveles que comprobar"


def test_cada_feature_lleva_lo_que_el_popup_necesita(datos_muestra, tmp_path):
    """El popup se pinta **desde el tile**, sin pedir nada al API: si falta un campo, sale vacío."""
    _, features = _features(tmp_path / "ccpp.geojsonseq")

    for feature in features[:50]:
        assert set(feature["properties"]) >= {
            "codigo", "nombre", "categoria", "distrito", "provincia",
            "ubigeo_distrito", "poblacion",
        }


def test_sin_poblacion_se_escribe_cero_no_nulo(datos_muestra, tmp_path):
    """El radio del símbolo se interpola sobre `poblacion`; con `null` MapLibre descarta el punto."""
    _, features = _features(tmp_path / "ccpp.geojsonseq")

    assert all(isinstance(f["properties"]["poblacion"], int) for f in features)


def test_las_capas_sin_tiles_no_se_anuncian_como_listas(datos_muestra):
    """Contrapartida del pipeline: el estado se pone a `ok` al terminar, no al empezar."""
    from apps.mapas.models import CapaCartografica

    for capa in CapaCartografica.objects.all():
        if capa.estado_tiles == CapaCartografica.EstadoTiles.OK:
            assert capa.archivo_tiles, f"«{capa.slug}» dice ok y no tiene archivo de tiles"
