"""Búsqueda con Meilisearch (spec 04).

Los siete índices se declaran **en un solo registro** con su queryset, sus atributos y su
constructor de documento. Todo lo demás —crear, configurar, reconstruir, sincronizar por
señal— se deriva de ahí: añadir un índice es añadir una entrada, no tocar cinco archivos.

La llave que usa el navegador es **search-only** y la genera `manage.py meili_setup`. Es segura
por diseño (solo búsqueda, solo los índices públicos); la master key nunca sale del backend.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

from django.conf import settings

from apps.core.sanitizar import a_texto_plano

#: Nombre de la llave search-only, solo para poder reconocerla en el panel de Meilisearch.
NOMBRE_LLAVE_BUSQUEDA = "frontend-search-only"

#: uid **fijo** de la llave search-only, y la razón de que la llave sea estable.
#:
#: Las llaves de Meilisearch son deterministas: `key` es el SHA-256 del uid con la master key. Con
#: un uid fijo, el mismo `MEILI_MASTER_KEY` devuelve siempre la misma llave, así que recrear el
#: volumen de Meilisearch o restaurar un respaldo **ya no invalida el bundle del frontend**.
#:
#: Cambiar este valor rota la llave: obliga a actualizar los dos `.env` y a reconstruir el frontend.
UID_LLAVE_BUSQUEDA = "3401f070-db11-4dd8-a6b5-1f1ea06033dc"


#: Segundos de espera para las consultas de **estado** (`disponible`, `estado_indices`).
#:
#: Sin timeout, un Meilisearch que acepta la conexión y no contesta —reindexando algo enorme,
#: swap agotando memoria, la red a medias— deja colgada la petición que preguntaba por él: la de
#: `/api/buscar/estado/` que hace el navegador en cada búsqueda, y la portada del admin. Una
#: comprobación de salud que se puede quedar esperando no es una comprobación de salud.
#:
#: **No se aplica a indexar**: `reconstruir` espera hasta 180 s por tarea y así debe seguir.
TIMEOUT_ESTADO = 3


def cliente(timeout: int | None = None):
    """Cliente con la master key. Solo para el backend."""
    import meilisearch

    if not settings.MEILI_MASTER_KEY:
        raise RuntimeError(
            "MEILI_MASTER_KEY no está configurada: sin ella no se puede administrar el índice."
        )
    return meilisearch.Client(settings.MEILI_URL, settings.MEILI_MASTER_KEY, timeout=timeout)


def cliente_url() -> str:
    """Solo para mensajes de error: decir «no responde» sin decir dónde no ayuda a nadie."""
    return settings.MEILI_URL


def disponible() -> bool:
    """¿Está Meilisearch arriba? El frontend degrada a DRF si no (spec 04)."""
    try:
        return bool(cliente(timeout=TIMEOUT_ESTADO).is_healthy())
    except Exception:  # noqa: BLE001 — la indisponibilidad es un estado, no un error
        return False


def _marca_tiempo(valor) -> int | None:
    """Fecha a unix timestamp: Meilisearch ordena por números, no por texto ISO."""
    if isinstance(valor, datetime):
        return int(valor.timestamp())
    if isinstance(valor, date):
        return int(datetime(valor.year, valor.month, valor.day).timestamp())
    return None


@dataclass
class Indice:
    slug: str
    etiqueta: str
    #: Ruta al modelo, como "medidas.Medida".
    modelo: str
    searchable: list[str]
    filterable: list[str]
    sortable: list[str]
    documento: Callable[[object], dict]
    #: Manager del que salen los documentos. Los editoriales usan `publicados`.
    manager: str = "publicados"
    select_related: list[str] = field(default_factory=list)

    def queryset(self):
        from django.apps import apps as django_apps

        modelo = django_apps.get_model(self.modelo)
        qs = getattr(modelo, self.manager).all()
        return qs.select_related(*self.select_related) if self.select_related else qs


# --- Constructores de documento --------------------------------------------
def _doc_medida(m) -> dict:
    return {
        "id": m.pk,
        "slug": m.slug,
        "titulo": m.titulo,
        "resumen_corto": m.resumen_corto,
        # El rich text se indexa como texto plano: buscar «qochas» no puede fallar porque la
        # palabra estuviera dentro de un <strong>.
        "contenido_texto": a_texto_plano(m.contenido),
        "comunidad": m.comunidad,
        "peligro": m.tipo_peligro.nombre if m.tipo_peligro_id else "",
        "ambito": m.get_ambito_display(),
        "resultado": m.get_resultado_display(),
        "provincia": m.distrito.provincia.nombre if m.distrito_id else "",
        "distrito": m.distrito.nombre if m.distrito_id else "",
        "palabras_clave": list(m.palabras_clave or []),
        "fecha": _marca_tiempo(m.publicado_en or m.creado_en),
        "url": f"/medidas/{m.slug}",
    }


def _doc_norma(n) -> dict:
    return {
        "id": n.pk,
        "slug": n.slug,
        "titulo": n.titulo,
        "resumen": n.resumen,
        "analisis_predes": n.analisis_predes or "",
        "contenido_texto": a_texto_plano(n.contenido),
        "numero": n.numero,
        "tipo": n.tipo.nombre if n.tipo_id else "",
        "ambito": n.get_ambito_display(),
        # El nombre y no el slug, igual que `tipo` y `ambito`: lo que se indexa es lo que el
        # visitante lee y escribe en el buscador.
        "entidad": n.entidad_emisora.nombre if n.entidad_emisora_id else "",
        "anio": n.fecha.year,
        "palabras_clave": list(n.palabras_clave or []),
        "fecha": _marca_tiempo(n.fecha),
        "url": f"/normativa/{n.slug}",
    }


def _doc_noticia(n) -> dict:
    return {
        "id": n.pk,
        "slug": n.slug,
        "titulo": n.titulo,
        "bajada": n.bajada,
        "cuerpo_texto": a_texto_plano(n.cuerpo),
        "tipo": n.get_tipo_display(),
        "autor": n.autor,
        "anio": n.fecha.year,
        "palabras_clave": list(n.palabras_clave or []),
        "fecha": _marca_tiempo(n.fecha),
        "url": f"/noticias/{n.slug}",
    }


def _doc_documento(d) -> dict:
    return {
        "id": d.pk,
        "titulo": d.titulo,
        "resumen": d.resumen,
        "autor_institucion": d.autor_institucion,
        "categoria": d.categoria.nombre if d.categoria_id else "",
        "anio": d.fecha_publicacion.year if d.fecha_publicacion else None,
        "fecha": _marca_tiempo(d.fecha_publicacion),
        "url": "/recursos",
    }


def _doc_video(v) -> dict:
    return {
        "id": v.pk,
        "titulo": v.titulo,
        "descripcion": v.descripcion,
        "tema": v.tema.nombre if v.tema_id else "",
        "fecha": _marca_tiempo(v.fecha),
        "url": "/videos",
    }


def _doc_evento(e) -> dict:
    return {
        "id": e.pk,
        "titulo": e.titulo,
        "descripcion": e.descripcion,
        "lugar": e.lugar,
        "modalidad": e.get_modalidad_display(),
        # `mes` facetable: el calendario filtra por mes, y hacerlo sobre el timestamp obligaría
        # a calcular rangos en el cliente.
        "mes": e.inicio.strftime("%Y-%m"),
        "inicio": _marca_tiempo(e.inicio),
        "url": "/eventos",
    }


def _doc_ccpp(c) -> dict:
    """Alimenta el autocompletado del buscador del mapa y del GeoSelector.

    Lleva `lat`/`lon` para que el visor haga `flyTo` con el resultado sin una segunda petición.
    """
    return {
        "id": c.codigo,
        "codigo": c.codigo,
        "nombre": c.nombre,
        "categoria": c.categoria,
        "distrito": c.distrito.nombre,
        "provincia": c.distrito.provincia.nombre,
        "ubigeo_distrito": c.distrito_id,
        "nivel_max": getattr(c, "nivel_max", None) or 0,
        "lat": c.lat,
        "lon": c.lon,
        "url": f"/peligros/{c.codigo}",
    }


INDICES: dict[str, Indice] = {
    "medidas": Indice(
        slug="medidas",
        etiqueta="Medidas",
        modelo="medidas.Medida",
        searchable=["titulo", "resumen_corto", "contenido_texto", "comunidad", "palabras_clave"],
        filterable=["peligro", "ambito", "resultado", "provincia", "distrito", "palabras_clave"],
        sortable=["fecha"],
        documento=_doc_medida,
        select_related=["tipo_peligro", "distrito__provincia"],
    ),
    "normativa": Indice(
        slug="normativa",
        etiqueta="Normativa",
        modelo="normativa.Norma",
        searchable=["titulo", "resumen", "analisis_predes", "numero", "contenido_texto",
                    "entidad"],
        filterable=["tipo", "ambito", "entidad", "anio", "palabras_clave"],
        sortable=["fecha"],
        documento=_doc_norma,
        select_related=["entidad_emisora", "tipo"],
    ),
    "noticias": Indice(
        slug="noticias",
        etiqueta="Noticias",
        modelo="contenidos.Noticia",
        searchable=["titulo", "bajada", "cuerpo_texto"],
        filterable=["tipo", "anio", "palabras_clave"],
        sortable=["fecha"],
        documento=_doc_noticia,
    ),
    "documentos": Indice(
        slug="documentos",
        etiqueta="Documentos",
        modelo="biblioteca.Documento",
        searchable=["titulo", "resumen", "autor_institucion"],
        filterable=["categoria", "anio"],
        sortable=["fecha"],
        documento=_doc_documento,
        select_related=["categoria"],
    ),
    "videos": Indice(
        slug="videos",
        etiqueta="Videos",
        modelo="contenidos.Video",
        searchable=["titulo", "descripcion"],
        filterable=["tema"],
        sortable=["fecha"],
        documento=_doc_video,
        select_related=["tema"],
    ),
    "eventos": Indice(
        slug="eventos",
        etiqueta="Eventos",
        modelo="contenidos.Evento",
        searchable=["titulo", "descripcion", "lugar"],
        filterable=["modalidad", "mes"],
        sortable=["inicio"],
        documento=_doc_evento,
    ),
    "ccpp": Indice(
        slug="ccpp",
        etiqueta="Centros poblados",
        modelo="territorio.CentroPoblado",
        searchable=["nombre", "distrito", "provincia"],
        filterable=["provincia", "distrito", "categoria"],
        sortable=[],
        documento=_doc_ccpp,
        # El padrón no es contenido editorial: no tiene estado ni manager `publicados`.
        manager="objects",
        select_related=["distrito__provincia"],
    ),
}

#: Índices que la llave search-only puede consultar. Son todos: el API público ya expone lo
#: mismo, y restringirla a menos obligaría a mantener dos listas que se desincronizarían.
INDICES_PUBLICOS = list(INDICES)

#: Índices que participan en la búsqueda global de `/buscar` (los CCPP van por su cuenta, en
#: el autocompletado del mapa: mezclar 8,968 topónimos con el contenido editorial ahogaría los
#: resultados que la persona está buscando).
INDICES_BUSQUEDA_GLOBAL = ["medidas", "normativa", "noticias", "documentos", "videos", "eventos"]


# --- Operaciones -----------------------------------------------------------
def ajustes(indice: Indice) -> dict:
    return {
        "searchableAttributes": indice.searchable,
        "filterableAttributes": indice.filterable,
        "sortableAttributes": indice.sortable,
        "displayedAttributes": ["*"],
        # Sin `stopWords` en español: quitar "de"/"la" rompería la búsqueda de una frase exacta
        # como «Ley de …», y la typo-tolerance ya cubre lo que de verdad importa.
        "typoTolerance": {"enabled": True, "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8}},
        "pagination": {"maxTotalHits": 1000},
    }


def _queryset_documentos(slug: str):
    indice = INDICES[slug]
    if slug != "ccpp":
        return indice.queryset()
    # `nivel_max` se anota en la consulta y no en el constructor: hacerlo por documento serían
    # 8,968 consultas sueltas.
    from django.db.models import Max

    return indice.queryset().annotate(nivel_max=Max("clasificaciones__nivel"))


def documentos(slug: str) -> list[dict]:
    indice = INDICES[slug]
    return [
        indice.documento(obj)
        for obj in _queryset_documentos(slug).iterator(chunk_size=1000)
    ]


def preparar(slug: str) -> None:
    """Crea el índice si falta y aplica sus ajustes. Idempotente."""
    cli = cliente()
    cli.create_index(slug, {"primaryKey": "id"})
    cli.wait_for_task(cli.index(slug).update_settings(ajustes(INDICES[slug])).task_uid)


def sincronizar(slug: str, pk) -> str:
    """Upsert o borrado de un documento, según el estado del objeto.

    Un objeto que deja de estar publicado se **borra** del índice. Si solo se actualizara,
    seguiría apareciendo en las búsquedas públicas después de despublicarlo, que es justo lo
    que el flujo editorial existe para evitar.
    """
    from django.apps import apps as django_apps

    indice = INDICES[slug]
    modelo = django_apps.get_model(indice.modelo)
    cli = cliente()

    if indice.manager == "objects":
        objeto = _queryset_documentos(slug).filter(pk=pk).first()
        visible = objeto is not None
    else:
        objeto = indice.queryset().filter(pk=pk).first()
        visible = objeto is not None

    if not visible:
        cli.index(slug).delete_document(str(pk))
        return "borrado"
    cli.index(slug).add_documents([indice.documento(objeto)])
    return "indexado"


def reconstruir(slug: str) -> int:
    """Reconstrucción total con swap por índice temporal.

    Borrar y volver a llenar el índice real dejaría al sitio con búsquedas vacías durante todo
    el proceso; con los 8,968 centros poblados eso son varios segundos de buscador roto.
    """
    indice = INDICES[slug]
    cli = cliente()
    temporal = f"{slug}-tmp"

    docs = documentos(slug)
    cli.wait_for_task(cli.create_index(temporal, {"primaryKey": "id"}).task_uid)
    cli.wait_for_task(cli.index(temporal).update_settings(ajustes(indice)).task_uid)
    for i in range(0, len(docs), 1000):
        tarea = cli.index(temporal).add_documents(docs[i : i + 1000])
        cli.wait_for_task(tarea.task_uid, timeout_in_ms=180_000)

    # El activo tiene que existir para poder intercambiarlo.
    cli.wait_for_task(cli.create_index(slug, {"primaryKey": "id"}).task_uid)
    cli.wait_for_task(cli.swap_indexes([{"indexes": [slug, temporal]}]).task_uid)
    cli.wait_for_task(cli.delete_index(temporal).task_uid)
    return len(docs)


def estado_indices() -> dict:
    """¿Está arriba la búsqueda, y está al día?

    Devuelve `{disponible, pendientes, al_dia, indices: [{slug, etiqueta, en_meili, en_bd,
    al_dia}]}`. Alimenta el panel del admin y `manage.py meili_estado`, que son las dos formas de
    responder esas preguntas sin abrir un shell.

    Por qué hace falta: **el desfase del índice es silencioso**. La sincronización va por señales
    hacia el worker (`core/signals.py`), así que si el worker estuvo caído, si Meilisearch no
    respondía al guardar, o si alguien escribió fuera del ORM, el índice se queda atrás y el único
    síntoma es «el buscador no encuentra algo que sí está publicado». Nadie se entera hasta que
    alguien lo nota.

    Se compara contra `queryset()`, el mismo del que salen los documentos: el número de la derecha
    es lo que **debería** estar indexado, no el total de la tabla.

    `pendientes` son las tareas que Meilisearch tiene en cola: justo después de un rebuild los
    conteos van con retraso, y eso es «indexando», no «desfasado».

    **No se usa `numberOfDocuments` de `/stats`, y esa es la parte que hay que no romper.** Está
    cacheado: tras vaciar un índice —comprobado en Meilisearch 1.15— sigue devolviendo el conteo
    anterior mientras la búsqueda ya no encuentra nada, así que una comprobación basada en él da el
    índice por bueno justo en el caso que tiene que detectar. El total exacto es el de
    `get_documents({"limit": 0})`, que no devuelve documentos y cuesta ~17 ms para los siete.

    **No lanza nunca.** Un buscador caído no puede tumbar la portada del admin.
    """
    vacio = {"disponible": False, "pendientes": 0, "al_dia": False, "indices": []}
    try:
        cli = cliente(timeout=TIMEOUT_ESTADO)
        pendientes = cli.get_tasks({"statuses": "enqueued,processing"}).total
    except Exception:  # noqa: BLE001 — la indisponibilidad es un estado, no un error
        return vacio

    indices = []
    for slug, indice in INDICES.items():
        try:
            en_meili = cli.index(slug).get_documents({"limit": 0}).total
        except Exception:  # noqa: BLE001 — el índice puede no existir todavía
            en_meili = None
        en_bd = indice.queryset().count()
        indices.append({
            "slug": slug,
            "etiqueta": indice.etiqueta,
            # `None` = el índice no existe todavía en Meilisearch, que no es lo mismo que 0
            # documentos: significa que `meili_setup` no ha llegado a correr contra esta instancia.
            "en_meili": en_meili,
            "en_bd": en_bd,
            "al_dia": en_meili == en_bd,
        })
    return {
        "disponible": True,
        "pendientes": pendientes,
        "al_dia": all(i["al_dia"] for i in indices),
        "indices": indices,
    }


def _crear_llave_busqueda(cli):
    return cli.create_key({
        "uid": UID_LLAVE_BUSQUEDA,
        "name": NOMBRE_LLAVE_BUSQUEDA,
        "description": "Solo búsqueda, para el frontend del Observatorio Kallpachakuy.",
        "actions": ["search"],
        "indexes": INDICES_PUBLICOS,
        "expiresAt": None,
    })


def _llave_al_dia(llave) -> bool:
    """La llave sirve tal cual: mismos permisos y mismos índices públicos.

    Si se añade un índice público, la llave existente no lo cubre y ese índice responde 403 **solo
    él**, con el resto de la búsqueda funcionando: un fallo parcial y silencioso.
    """
    return set(llave.actions) == {"search"} and set(llave.indexes) == set(INDICES_PUBLICOS)


def llave_busqueda() -> str:
    """Devuelve la llave search-only, creándola si no existe.

    Se identifica **por su uid fijo**, no por su nombre, y eso es lo que la hace estable: las
    llaves de Meilisearch son deterministas —`key` es el SHA-256 del uid con la master key—, así
    que el mismo `MEILI_MASTER_KEY` con el mismo uid devuelve siempre la misma llave. Antes se
    creaba con uid aleatorio y por tanto vivía en el volumen de Meilisearch: recrear el volumen (o
    restaurar un respaldo) cambiaba la llave y **dejaba el bundle del frontend con una llave que ya
    no existía**, con el buscador cayendo al fallback de DRF, las facetas de `/medidas` sin conteos
    y el autocompletado de lugares sin resultados. Solo el primero avisaba.

    Idempotente: `meili_setup` corre en cada arranque del backend.
    """
    cli = cliente()

    actual = None
    try:
        actual = cli.get_key(UID_LLAVE_BUSQUEDA)
    except Exception:  # noqa: BLE001 — «no existe» es un estado, y el SDK lo comunica lanzando
        actual = None

    if actual is not None:
        if _llave_al_dia(actual):
            return actual.key
        # `PATCH /keys/{uid}` solo admite `name` y `description`: para cambiar los índices hay que
        # borrar y volver a crear. Con el mismo uid la llave sale idéntica, así que el frontend
        # que ya esté desplegado sigue siendo válido.
        cli.delete_key(UID_LLAVE_BUSQUEDA)

    # Llaves heredadas de cuando el uid era aleatorio: se retiran para no dejar dos válidas.
    for llave in cli.get_keys().results:
        if llave.name == NOMBRE_LLAVE_BUSQUEDA and llave.uid != UID_LLAVE_BUSQUEDA:
            cli.delete_key(llave.uid)

    return _crear_llave_busqueda(cli).key
