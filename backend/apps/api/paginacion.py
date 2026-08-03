from rest_framework.pagination import PageNumberPagination


class PaginacionEstandar(PageNumberPagination):
    """Paginación del contrato (spec 02): `page`/`page_size`, default 50, máximo 200.

    El techo importa: sin él, `?page_size=100000` convierte cualquier listado en un export
    completo sin pasar por el throttling de descargas.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
