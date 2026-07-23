"""Cliente Gemini para autocompletar resúmenes de documentos PDF.

Esqueleto documentado — se completa cuando exista la app `biblioteca`
(modelo Documento). Contrato:

    generar_resumen(archivo_pdf: bytes | None, url_pdf: str | None) -> str

- Modelo: gemini-2.5-flash (lee PDF nativamente, sin extracción local).
- PDFs < 20 MB van inline; mayores, vía Files API.
- URL externa: se descarga server-side (timeout 30 s, máx 50 MB).
- Errores/timeout: el llamador (tarea django-tasks) captura y guarda en
  log_ia; la publicación nunca depende de Gemini.
"""
from django.conf import settings

PROMPT_RESUMEN = (
    "Eres analista de gestión del riesgo de desastres y adaptación al cambio "
    "climático en Perú. Resume este documento en 120-180 palabras, en español "
    "claro, para el público del Observatorio Kallpachakuy de PREDES (Cusco): "
    "qué es, qué establece o encuentra, y por qué importa para la GRD/ACC "
    "regional. Sin viñetas ni encabezados. Si el documento no es legible, "
    "responde únicamente ILEGIBLE."
)


def generar_resumen(archivo_pdf: bytes | None = None, url_pdf: str | None = None) -> str:
    """Genera el resumen de un PDF con gemini-2.5-flash."""
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY no configurada en backend/.env")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    if archivo_pdf is None and url_pdf:
        import urllib.request

        with urllib.request.urlopen(url_pdf, timeout=30) as resp:  # noqa: S310
            archivo_pdf = resp.read(50 * 1024 * 1024)
    if not archivo_pdf:
        raise ValueError("Se requiere un PDF (bytes) o una URL descargable")

    respuesta = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=archivo_pdf, mime_type="application/pdf"),
            PROMPT_RESUMEN,
        ],
    )
    texto = (respuesta.text or "").strip()
    if not texto or texto.upper().startswith("ILEGIBLE"):
        raise ValueError("Gemini no pudo leer el documento")
    return texto
