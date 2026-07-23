"""Cliente Meilisearch del proyecto.

Esqueleto documentado — la sincronización por señales y el comando
`meili_rebuild` se implementan junto con las apps editoriales.

Índices previstos (ver _specs/04-busqueda.md):
- `ccpp` (8,968 centros poblados; autocompletado geográfico)
- `medidas`, `normativa`, `documentos`, `noticias`, `videos`, `eventos`
  (solo contenido publicado; facetas por índice)

`meili_setup` (comando por crear) debe: crear índices, configurar
searchable/filterable/sortable attributes y emitir la llave search-only
que usa el frontend vía /search/.
"""
import meilisearch
from django.conf import settings


def cliente() -> meilisearch.Client:
    return meilisearch.Client(settings.MEILI_URL, settings.MEILI_MASTER_KEY)


def indexar(indice: str, documentos: list[dict], clave_primaria: str = "id") -> None:
    """Upsert de documentos en un índice (crea el índice si no existe)."""
    cliente().index(indice).add_documents(documentos, primary_key=clave_primaria)


def eliminar(indice: str, doc_id) -> None:
    cliente().index(indice).delete_document(doc_id)
