"""Panel de inicio del admin (spec 03).

Responde las preguntas que PREDES se hará al entrar: qué hay pendiente de revisar, qué se está
consultando, y si los datos y los tiles están al día. Se apoya en `ResumenDiario`, no en
`EventoUso`, porque los eventos crudos se purgan a los 90 días y el panel tiene que seguir
mostrando el mes pasado.
"""
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone


def datos_panel(request, contexto: dict | None = None) -> dict:
    """Callback de `UNFOLD["DASHBOARD_CALLBACK"]`.

    Unfold lo llama con `(request, context)` y espera **el contexto completo de vuelta**, no
    solo los añadidos: devolver un diccionario nuevo dejaría la plantilla sin las variables del
    admin.
    """
    contexto = dict(contexto or {})
    contexto.update(_metricas(request))
    return contexto


def _metricas(request) -> dict:
    from apps.core.services import meili
    from apps.biblioteca.models import Documento
    from apps.contenidos.models import Evento, Noticia, Video
    from apps.datasets.models import DatasetUpload
    from apps.mapas.models import CapaCartografica
    from apps.medidas.models import Medida
    from apps.metricas.models import ResumenDiario, TipoEventoUso
    from apps.normativa.models import Norma
    from apps.peligros.models import ClasificacionPeligro
    from apps.territorio.models import CentroPoblado

    desde = timezone.localdate() - timedelta(days=30)
    resumenes = ResumenDiario.objects.filter(fecha__gte=desde)

    def total(tipo: str) -> int:
        return resumenes.filter(tipo=tipo).aggregate(t=Sum("conteo"))["t"] or 0

    def top(tipo: str, campo: str, n: int = 8):
        return list(
            resumenes.filter(tipo=tipo)
            .exclude(**{f"{campo}": ""})
            .values(campo)
            .annotate(conteo=Sum("conteo"))
            .order_by("-conteo")[:n]
        )

    # Contenido por estado: es la cola de trabajo del equipo editorial.
    modelos = [
        ("Medidas", Medida), ("Normas", Norma), ("Noticias", Noticia),
        ("Videos", Video), ("Eventos", Evento), ("Documentos", Documento),
    ]
    contenido = []
    pendientes_revision = 0
    for nombre, modelo in modelos:
        conteos = {
            estado: modelo.objects.filter(estado=estado).count()
            for estado in ("borrador", "revision", "publicado", "archivado")
        }
        pendientes_revision += conteos["revision"]
        contenido.append({"nombre": nombre, **conteos})

    ultima_carga = DatasetUpload.objects.filter(estado="activo").order_by("-activado_en").first()
    capas_con_error = CapaCartografica.objects.filter(estado_tiles="error")

    def filas(tipo: str, campo: str):
        return [
            {"etiqueta": f[campo], "conteo": f["conteo"]} for f in top(tipo, campo)
        ]

    return {
        "pendientes_revision": pendientes_revision,
        "contenido": contenido,
        "cifras": [
            ("Visitas", total(TipoEventoUso.PAGEVIEW)),
            ("Búsquedas", total(TipoEventoUso.BUSQUEDA)),
            ("Ayudas memoria", total(TipoEventoUso.DESCARGA_PDF)),
            ("Exports Excel", total(TipoEventoUso.EXPORT_EXCEL)),
            ("Documentos", total(TipoEventoUso.DESCARGA_DOCUMENTO)),
        ],
        "tablas": [
            {"titulo": "Páginas más vistas", "filas": filas(TipoEventoUso.PAGEVIEW, "ruta")},
            {"titulo": "Búsquedas más frecuentes",
             "filas": filas(TipoEventoUso.BUSQUEDA, "detalle")},
            # Qué distritos se están llevando a mesas técnicas: es lo que el TDR busca cuando
            # pide "métricas internas de uso".
            {"titulo": "Distritos con más ayudas memoria",
             "filas": filas(TipoEventoUso.DESCARGA_PDF, "detalle")},
        ],
        "datos": {
            "ccpp": CentroPoblado.objects.count(),
            "clasificaciones": ClasificacionPeligro.objects.count(),
            "ultima_carga": ultima_carga,
        },
        "capas_con_error": capas_con_error,
        "sin_metricas": not resumenes.exists(),
        # Estado de la búsqueda: si está arriba y si lo indexado cuadra con la base. Es la única
        # forma que tiene PREDES de enterarse de un índice desfasado, que por sí solo no da ningún
        # síntoma más que «el buscador no encuentra algo que sí está publicado».
        "buscador": meili.estado_indices(),
    }
