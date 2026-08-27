"""Sitio, mapas, comparador, métricas e Inversión (spec 02).

Aquí viven las garantías de degradación: qué responde el API cuando algo **no** está —una capa a
medio generar, la ventana de inversión sin datos, un servicio de búsqueda caído—. Son los casos
que deciden si el sitio se lee como «en preparación» o como «roto».
"""
import pytest

pytestmark = pytest.mark.django_db


# --- /api/sitio/ ------------------------------------------------------------


def test_sitio_trae_todo_el_cascaron_en_una_peticion(api):
    """El frontend lo pide una vez al montar el layout; partirlo añadiría round-trips."""
    datos = api.get("/api/sitio/").json()

    assert set(datos) == {"config", "bloques", "menu", "hero"}
    assert set(datos["menu"]) == {"top", "header", "footer"}
    assert datos["bloques"], "el seed no dejó bloques de texto"


def test_sitio_se_puede_cachear(api):
    """Es la primera petición de cada visita: sin cabecera de caché se repite en cada página."""
    respuesta = api.get("/api/sitio/")

    assert "max-age" in respuesta["Cache-Control"]


def test_el_menu_omite_los_enlaces_ocultos(api):
    """`visible=False` es cómo se retira una sección sin perder su configuración (ADR-P1).

    Prioridades está así. Si el API los devolviera igual, ocultar algo obligaría a tocar código.
    """
    from apps.sitio.models import EnlaceMenu

    ocultos = list(
        EnlaceMenu.objects.filter(visible=False).values_list("url", flat=True)
    )
    datos = api.get("/api/sitio/").json()
    publicados = {
        e["url"] for zona in datos["menu"].values() for e in zona
    }

    assert ocultos, "el seed debería dejar al menos Prioridades oculta"
    assert not publicados & set(ocultos)


def test_inversion_sigue_visible_en_el_menu_con_su_pagina_en_espera(api):
    """Sin datos publicados no es oculta (ADR-D4): la sección se anuncia y explica que faltan."""
    datos = api.get("/api/sitio/").json()
    urls = {e["url"] for e in datos["menu"]["header"]}

    assert "/inversion" in urls


def test_el_hero_solo_muestra_slides_publicados(api):
    """Los slides pasan por el mismo flujo editorial que el contenido."""
    from apps.sitio.models import HeroSlide

    HeroSlide.objects.create(titulo="Borrador de portada", orden=99)
    HeroSlide.objects.create(
        titulo="Portada vigente", orden=1, estado=HeroSlide.Estado.PUBLICADO
    )

    titulos = [s["titulo"] for s in api.get("/api/sitio/").json()["hero"]]

    assert "Portada vigente" in titulos
    assert "Borrador de portada" not in titulos


# --- /api/mapas/capas/ ------------------------------------------------------


def test_solo_se_anuncian_las_capas_con_tiles_listos(api):
    """Una capa a medio generar no se ofrece: el visor pediría un .pmtiles inexistente.

    MapLibre no falla de forma visible ante eso — llena la consola de errores por cada tesela y
    el usuario ve un mapa incompleto sin saber por qué.
    """
    from apps.mapas.models import CapaCartografica

    CapaCartografica.objects.update(estado_tiles=CapaCartografica.EstadoTiles.OK)
    total = CapaCartografica.objects.count()
    assert total, "el seed no dejó capas cartográficas"

    una = CapaCartografica.objects.first()
    una.estado_tiles = CapaCartografica.EstadoTiles.PENDIENTE
    una.save()

    slugs = {c["slug"] for c in api.get("/api/mapas/capas/").json()}

    assert len(slugs) == total - 1
    assert una.slug not in slugs


def test_cada_capa_trae_url_absoluta_y_estilo_de_maplibre(api, settings):
    """La URL es absoluta porque la SPA vive en otro dominio (ADR-A14).

    Y el estilo viene del servidor: es lo que permite a PREDES cambiar el color de una capa sin
    que nadie despliegue.
    """
    from apps.mapas.models import CapaCartografica

    CapaCartografica.objects.update(estado_tiles=CapaCartografica.EstadoTiles.OK)
    capas = api.get("/api/mapas/capas/").json()

    assert capas
    for capa in capas:
        assert set(capa) >= {"slug", "nombre", "url", "tipo_geometria", "estilo"}
        assert capa["url"].startswith(settings.BACKEND_URL)
        assert capa["url"].endswith(".pmtiles")
        assert "tipo" in capa["estilo"]


# --- Comparador -------------------------------------------------------------


def test_el_comparador_exige_entre_dos_y_cuatro_distritos(api, datos_muestra):
    """Menos de dos no es comparar; más de cuatro no cabe en pantalla ni se lee."""
    from apps.territorio.models import Distrito

    ubigeos = list(Distrito.objects.values_list("ubigeo", flat=True)[:5])

    assert api.get("/api/comparador/distritos/").status_code == 400
    assert api.get(f"/api/comparador/distritos/?ubigeos={ubigeos[0]}").status_code == 400
    assert api.get(
        f"/api/comparador/distritos/?ubigeos={','.join(ubigeos[:2])}"
    ).status_code == 200
    assert api.get(f"/api/comparador/distritos/?ubigeos={','.join(ubigeos)}").status_code == 400


def test_el_comparador_avisa_de_un_ubigeo_inexistente(api, datos_muestra):
    """Un ubigeo mal escrito tiene que decirse, no colarse como columna vacía."""
    respuesta = api.get("/api/comparador/distritos/?ubigeos=080101,089999")

    assert respuesta.status_code == 400
    assert "089999" in str(respuesta.json())


def test_el_comparador_declara_que_inversion_no_esta_disponible(api, datos_muestra):
    from apps.territorio.models import Distrito

    ubigeos = ",".join(Distrito.objects.values_list("ubigeo", flat=True)[:2])
    datos = api.get(f"/api/comparador/distritos/?ubigeos={ubigeos}").json()

    assert datos["inversion_disponible"] is False


# --- Inversión (ADR-D4) -----------------------------------------------------


def test_inversion_responde_no_disponible_con_motivo(api):
    """La forma importa: el frontend dibuja su estado vacío sin casos especiales.

    Y el motivo se publica porque «no disponible» sin explicación se lee como avería.
    """
    datos = api.get("/api/inversion/").json()

    assert datos["disponible"] is False
    assert datos["motivo"]


# --- Búsqueda ---------------------------------------------------------------


def test_el_fallback_de_busqueda_agrupa_por_tipo(api):
    """`/api/buscar/` responde sin Meilisearch: es el plan B del buscador.

    Un sitio que dice «no se pudo buscar» se lee como roto, no como degradado, y el buscador es
    la puerta de entrada al contenido.
    """
    from apps.medidas.models import Medida
    from apps.peligros.models import TipoPeligro

    Medida.objects.create(
        slug="reforestacion-en-quispicanchi",
        titulo="Reforestación en Quispicanchi",
        tipo_peligro=TipoPeligro.objects.get(slug="heladas"),
        ambito=Medida.Ambito.DISTRITAL,
        resultado=Medida.Resultado.EXITO,
        resumen_corto="Especies nativas en cabecera de cuenca.",
        estado=Medida.Estado.PUBLICADO,
    )

    datos = api.get("/api/buscar/?q=Reforestación").json()
    grupos = {g["indice"]: g for g in datos["grupos"]}

    assert datos["motor"] == "drf"
    assert "medidas" in grupos
    assert any("Reforestación" in r["titulo"] for r in grupos["medidas"]["resultados"])
    # Los grupos vacíos no viajan: el cliente pinta una sección por grupo recibido.
    assert all(g["resultados"] for g in datos["grupos"])


def test_la_busqueda_encuentra_centros_poblados_por_nombre(api, datos_muestra):
    """El buscador de lugares es lo que lleva del nombre de un caserío a su ficha de peligros."""
    datos = api.get("/api/buscar/?q=cusco").json()
    grupos = {g["indice"]: g for g in datos["grupos"]}

    assert grupos["ccpp"]["resultados"]
    assert grupos["ccpp"]["resultados"][0]["url"].startswith("/peligros/")


def test_una_busqueda_vacia_no_devuelve_el_catalogo_entero(api):
    datos = api.get("/api/buscar/?q=").json()

    assert datos["total"] == 0
    assert datos["grupos"] == []


def test_la_busqueda_no_encuentra_lo_no_publicado(api):
    from apps.medidas.models import Medida
    from apps.peligros.models import TipoPeligro

    Medida.objects.create(
        slug="medida-en-borrador",
        titulo="Cosecha de agua en borrador",
        tipo_peligro=TipoPeligro.objects.get(slug="sequia"),
        ambito=Medida.Ambito.DISTRITAL,
        resultado=Medida.Resultado.EXITO,
        resumen_corto="Todavía en redacción.",
    )

    datos = api.get("/api/buscar/?q=cosecha").json()

    assert datos["total"] == 0


def test_el_estado_de_la_busqueda_se_puede_consultar(api):
    """El frontend decide con esto si ataca Meilisearch o cae al fallback.

    Sin este endpoint tendría que intentarlo y esperar el timeout para descubrir que está caído,
    y ese retraso lo paga el usuario en cada búsqueda.
    """
    datos = api.get("/api/buscar/estado/").json()

    assert set(datos) == {"meili_disponible", "indices", "indice_lugares"}
    assert isinstance(datos["meili_disponible"], bool)


def test_con_meilisearch_caido_el_estado_no_ofrece_indices(api, monkeypatch):
    """El frontend tiene que poder distinguir «no hay motor» de «no hay resultados»."""
    from apps.core.services import meili

    monkeypatch.setattr(meili, "disponible", lambda: False)
    datos = api.get("/api/buscar/estado/").json()

    assert datos["meili_disponible"] is False
    assert datos["indices"] == []
    assert datos["indice_lugares"] == ""


# --- Métricas (ADR-A11) -----------------------------------------------------


def test_el_beacon_registra_sin_guardar_datos_personales(api):
    """Acepta `form-encoded` a propósito: con JSON el navegador exige preflight y `sendBeacon`
    no siempre puede completarlo, así que las métricas se perdían en silencio.

    Y no se guarda PII: la sesión es un hash de IP+UA que además **cambia cada día**, así que el
    mismo visitante no es correlacionable entre jornadas.
    """
    from apps.metricas.models import EventoUso

    respuesta = api.post(
        "/api/metricas/evento/",
        {"tipo": "pageview", "ruta": "/peligros"},
        format="multipart",
    )
    evento = EventoUso.objects.get()

    assert respuesta.status_code == 204
    assert evento.ruta == "/peligros"
    assert len(evento.session_hash) == 12
    for campo in ("ip", "user_agent", "email", "usuario"):
        assert not hasattr(evento, campo), f"EventoUso no debería guardar «{campo}»"


def test_el_hash_de_sesion_lleva_la_fecha_dentro(api):
    """La fecha entra en la semilla, y es lo que impide seguir a un visitante entre jornadas.

    Se reconstruye el hash a mano: comprobar que «cambia mañana» exigiría viajar en el tiempo,
    mientras que reproducir la semilla demuestra directamente que la fecha está dentro. Si alguien
    la quitara para «hacerlo estable», el hash pasaría a ser un identificador permanente.
    """
    import hashlib
    from datetime import date

    from django.test import RequestFactory

    from apps.api.views.sitio import _hash_sesion

    peticion = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.1", HTTP_USER_AGENT="navegador-de-prueba"
    )
    esperado = hashlib.sha256(
        f"10.0.0.1|navegador-de-prueba|{date.today().isoformat()}".encode()
    ).hexdigest()[:12]

    assert _hash_sesion(peticion) == esperado


def test_el_hash_de_sesion_distingue_visitantes_dentro_del_dia(api):
    from django.test import RequestFactory

    from apps.api.views.sitio import _hash_sesion

    fabrica = RequestFactory()
    uno = _hash_sesion(fabrica.get("/", REMOTE_ADDR="10.0.0.1", HTTP_USER_AGENT="a"))
    otro = _hash_sesion(fabrica.get("/", REMOTE_ADDR="10.0.0.2", HTTP_USER_AGENT="a"))

    assert uno != otro


def test_el_beacon_rechaza_un_tipo_de_evento_inventado(api):
    from apps.metricas.models import EventoUso

    respuesta = api.post(
        "/api/metricas/evento/", {"tipo": "loquesea", "ruta": "/"}, format="multipart"
    )

    assert respuesta.status_code == 400
    assert not EventoUso.objects.exists()
