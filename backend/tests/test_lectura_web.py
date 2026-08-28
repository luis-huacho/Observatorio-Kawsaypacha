"""La lectura de una página ajena: extracción de texto y guarda anti-SSRF.

Vivían en `test_noticias_ia.py` y se mudaron aquí con su código cuando normativa necesitó lo mismo
(ADR-D8). Se prueban **una vez**, no una por app: son la mitad genérica, y duplicar la prueba de
un control de seguridad garantiza que una de las dos copias se quede atrás.

Lo que protegen son dos fallos que no dan ningún error:

1. Que la extracción devuelva un texto ilegible —palabras pegadas, `<script>` incluido— y la IA
   redacte a partir de basura sin que nada falle.
2. Que la descarga acepte un destino interno y el formulario del admin se convierta en una vía
   para sondear la red privada desde dentro.
"""
import pytest

from apps.core import lectura_web

PAGINA = """<html><head>
<meta property="og:image" content="https://medio.pe/foto.jpg">
<script>rastreador()</script><style>.a{color:red}</style>
</head><body><nav>Portada</nav>
<h1>Huaicos en Quispicanchi</h1>
<p>Las lluvias del fin de semana activaron quebradas en tres distritos de la provincia de
Quispicanchi, con daños en viviendas y vías de acceso segun el reporte del COER Cusco.</p>
</body></html>"""


def test_la_extraccion_descarta_scripts_y_separa_los_bloques():
    """Sin el salto previo, nh3 pega las palabras entre sí y el prompt queda ilegible."""
    texto = lectura_web.extraer_texto(PAGINA)

    assert "rastreador" not in texto
    assert "color:red" not in texto
    assert "Huaicos en Quispicanchi" in texto
    assert "PortadaHuaicos" not in texto


@pytest.mark.parametrize(
    "url",
    [
        "ftp://medio.pe/nota",
        "file:///etc/passwd",
        "http://127.0.0.1/admin",
        "http://[::1]/admin",
    ],
)
def test_no_se_puede_apuntar_la_descarga_a_la_red_interna(url):
    """La URL la escribe un editor y la petición la hace el servidor.

    Sin esto, el formulario sería una vía para sondear la red privada desde dentro
    (`http://meilisearch:7700`, `http://db:5432`) con una cuenta de editor cualquiera.
    """
    with pytest.raises(ValueError):
        lectura_web.comprobar_destino(url)


def test_una_url_publica_si_pasa():
    lectura_web.comprobar_destino("https://www.gob.pe/senamhi")


@pytest.mark.parametrize(
    ("crudo", "tipo", "esperado"),
    [
        (b"%PDF-1.7\n...", "", True),
        (b"cualquier cosa", "application/pdf", True),
        # El caso real que obliga a mirar el contenido: servidores del Estado que sirven el PDF
        # declarando un tipo genérico.
        (b"%PDF-1.4", "application/octet-stream", True),
        (b"<html><body>hola</body></html>", "text/html", False),
        (b"<html>", "", False),
    ],
)
def test_un_pdf_se_reconoce_por_la_cabecera_o_por_los_bytes(crudo, tipo, esperado):
    assert lectura_web.es_pdf(crudo, tipo) is esperado
