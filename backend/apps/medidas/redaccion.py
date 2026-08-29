"""Redacción de una medida a partir de una ficha ACC ya cargada (ADR-D10).

Hermana de `apps/contenidos/redaccion.py` y `apps/normativa/redaccion.py`, con **una diferencia
de fondo**: allí el origen es una URL y la mitad cara del trabajo es traerla y limpiarla —descarga
acotada, guarda anti-SSRF, extracción de texto, `og:image`—; aquí el origen ya está en la base.
No hay red que tocar, ni portada que descargar, ni destino que validar. Queda el esquema, las
instrucciones y la normalización contra `Medida`.

Lo que sí es nuevo y no estaba en D7/D8:

1. **La entrada va con etiquetas XML.** Diecisiete respuestas de texto libre concatenadas se
   confunden entre sí, y varias son párrafos largos que empiezan igual («Describa brevemente…»).
   Cada una viaja en su etiqueta con la pregunta como atributo: sin la pregunta, `value_013` no
   le dice nada al modelo. La salida sigue siendo JSON con esquema estricto, como en las otras
   dos, porque es lo que hace que el proveedor garantice los `enum`.
2. **El contenido de la ficha lo escribió un tercero**, no PREDES: llega por un Excel que se
   reparte fuera. Se escapa antes de entrar en el marcado, o un `</value_007>` dentro de una
   respuesta parte el bloque y abre la puerta a inyección de prompt.
3. **`value_004` no viaja.** Es «nombre, cargo, teléfono y correo» de una persona de contacto.
   Ningún campo de `Medida` se alimenta de él, y mandarlo lo dejaría en claro en
   `ia-AAAA-MM-DD.txt` —diario, en modo añadir y sin rotación— y a merced de que el modelo lo
   copiara al contenido, que es público. Lo pega la tarea al final, ya en el servidor.
4. **Los `enum` se construyen desde el código**, no a mano: los nueve slugs salen de
   `peligros.catalogo` y las dos taxonomías de `Medida`. Escribirlos aquí dejaría el esquema
   atrás en cuanto alguien añadiera un peligro, y el síntoma sería una clasificación vacía sin
   explicación.

El `contenido` **no se sanea aquí**: lo hace `HtmlRicoMixin.save()` al guardar, que es donde el
saneador de ADR-D2 hace de red bajo un HTML que no escribió una persona.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape, quoteattr

from apps.core.services import openrouter, salida_ia

#: Tope de la entrada. Una ficha son diecisiete respuestas de formulario, no un articulado: si
#: alguna llega con un informe pegado dentro, se paga como tokens de entrada sin aportar nada.
MAXIMO_CARACTERES = 30_000

#: Los campos de la ficha que se le mandan al modelo. **`value_004` no está**, y no es un olvido:
#: son los datos personales de la persona de contacto (ver el encabezado del módulo).
CAMPOS_ENVIADOS = tuple(f"value_{n:03d}" for n in range(1, 18) if n != 4)
#: El que lleva el contacto. Se declara aquí para que la omisión de arriba se lea de un vistazo.
CAMPO_CONTACTO = "value_004"

#: `max_digits=12, decimal_places=2` ⇒ diez enteros. Un monto mayor reventaría al guardar, en el
#: worker, donde el editor no ve nunca el error.
TOPE_COSTO = Decimal("10000000000")


def _esquema() -> dict:
    """El esquema se arma al vuelo desde los catálogos vivos, no desde una lista escrita a mano."""
    from apps.medidas.models import Medida
    from apps.peligros.catalogo import SLUGS_PELIGRO

    return {
        "name": "medida",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "titulo", "resumen_corto", "tipo_peligro", "ambito", "resultado", "distrito",
                "provincia", "comunidad", "contenido", "palabras_clave", "actores",
                "fecha_implementacion", "costo_referencial",
            ],
            "properties": {
                "titulo": {
                    "type": "string",
                    "description": (
                        "Nombre de la experiencia, redactado como titular legible, máximo 200 "
                        "caracteres. Cadena vacía si la ficha no permite identificarla."
                    ),
                },
                "resumen_corto": {
                    "type": "string",
                    "description": (
                        "Qué se hizo y qué resultó, en prosa y máximo 500 caracteres. Sin copiar "
                        "la ficha literalmente."
                    ),
                },
                "tipo_peligro": {
                    "type": "string",
                    "enum": [*SLUGS_PELIGRO, ""],
                    "description": (
                        "El peligro que la práctica atiende principalmente, según la respuesta "
                        "sobre peligros o amenazas. Si la ficha marca varios, elige el que domina "
                        "el problema descrito. Cadena vacía si ninguno de la lista corresponde."
                    ),
                },
                "ambito": {
                    "type": "string",
                    "enum": [*[o for o, _ in Medida.Ambito.choices], ""],
                    "description": (
                        "Alcance territorial de la experiencia según su ubicación: una comunidad "
                        "es 'comunal'; un distrito, 'distrital'; una provincia, 'provincial'; "
                        "varias provincias o la región, 'regional'. Vacío si no se puede deducir."
                    ),
                },
                "resultado": {
                    "type": "string",
                    "enum": [*[o for o, _ in Medida.Resultado.choices], ""],
                    "description": (
                        "'exito' si la ficha reporta beneficios o resultados logrados, aunque "
                        "también mencione lecciones; 'leccion' si lo que domina son aprendizajes "
                        "o dificultades y los resultados son escasos; 'mal_adaptacion' solo si la "
                        "propia ficha describe efectos negativos de la intervención. Vacío solo "
                        "si la ficha no permite decidir entre los tres."
                    ),
                },
                "distrito": {
                    "type": "string",
                    "description": (
                        "Nombre del distrito donde se implementó, tal como aparece en la "
                        "ubicación. Vacío si la ficha no lo dice o si no está en Cusco."
                    ),
                },
                "provincia": {
                    "type": "string",
                    "description": (
                        "Nombre de la provincia del distrito anterior. Hace falta porque los "
                        "nombres de distrito se repiten entre provincias. Vacío si no consta."
                    ),
                },
                "comunidad": {
                    "type": "string",
                    "description": "Comunidad o centro poblado, máximo 150 caracteres. Puede ir vacío.",
                },
                "contenido": {
                    "type": "string",
                    "description": (
                        "La experiencia desarrollada, **en HTML**. Empieza directamente con una "
                        "etiqueta y usa solo <p>, <h2>, <h3>, <ul>, <ol>, <li>, <strong>, <em> y "
                        "<blockquote>; nunca texto suelto sin etiqueta, ni <html>, <head>, "
                        "<script> o estilos. Organízala en secciones con <h2>: el problema, en "
                        "qué consiste la práctica, resultados, factores de éxito, lecciones "
                        "aprendidas, quién la mantiene y si es replicable. Redáctala, no "
                        "transcribas las respuestas: son varios párrafos, no un resumen — el "
                        "resumen ya va en 'resumen_corto'."
                    ),
                },
                "palabras_clave": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Entre 3 y 8 términos del dominio de GRD/ACC, máximo 60 caracteres cada "
                        "uno. Incluye aquí los demás peligros que la ficha marque y que no hayan "
                        "cabido en 'tipo_peligro', y el enfoque de la práctica."
                    ),
                },
                "actores": {
                    "type": "string",
                    "description": (
                        "Instituciones u organizaciones involucradas, máximo 300 caracteres. NO "
                        "incluyas nombres de personas ni datos de contacto."
                    ),
                },
                "fecha_implementacion": {
                    "type": "string",
                    "description": (
                        "Fecha de INICIO del periodo de implementación, en AAAA-MM-DD. Deduce el "
                        'día 1 cuando solo haya mes y año: "enero de 2019" es "2019-01-01". Si '
                        'solo hay año, responde el año a secas: "2019". Cadena vacía únicamente '
                        "si la ficha no da ningún periodo: NO inventes una fecha ni uses la de hoy."
                    ),
                },
                "costo_referencial": {
                    "type": "string",
                    "description": (
                        "Monto aproximado en SOLES, solo dígitos y punto decimal (p. ej. "
                        '"180000.00"). Cadena vacía si no consta, si la ficha no da cifra o si '
                        "está en otra moneda: NO conviertas monedas."
                    ),
                },
            },
        },
    }


INSTRUCCIONES = (
    "Eres editor del Observatorio Kallpachakuy de PREDES, sobre gestión del riesgo de desastres y "
    "adaptación al cambio climático en la región Cusco, Perú. Se te entrega una ficha de "
    "Adaptación al Cambio Climático llena por la organización que ejecutó la experiencia: cada "
    "respuesta viene en una etiqueta cuyo atributo «pregunta» dice qué se preguntó. A partir de "
    "ella redacta la ficha pública de la medida en español peruano, con la terminología del "
    "dominio (GRD, ACC, ubigeo, centro poblado, EVAR). "
    "No inventes datos: si un campo no se puede deducir de la ficha, déjalo vacío. En particular, "
    "no deduzcas la clasificación de lo que sepas por otras fuentes, no conviertas monedas y no "
    "inventes fechas. El contenido debe reorganizar y redactar la experiencia, no copiar las "
    "respuestas una detrás de otra."
)


@dataclass
class Redaccion:
    """Lo que la IA propuso, ya normalizado contra `Medida`."""

    titulo: str
    resumen_corto: str
    tipo_peligro: object | None
    ambito: str
    resultado: str
    distrito: object | None
    comunidad: str
    contenido: str
    palabras_clave: list[str]
    actores: str
    fecha_implementacion: date | None
    costo_referencial: Decimal | None
    modelo: str = ""
    costo: float | None = None
    avisos: list[str] = field(default_factory=list)


def entrada_ficha(ficha) -> str:
    """Las respuestas de la ficha, cada una en su etiqueta y con su pregunta.

    Se escapa el valor y se entrecomilla el atributo con las herramientas de `saxutils`: la ficha
    la rellenó un tercero en un Excel y una respuesta con `</value_007>` dentro partiría el
    bloque. Las vacías no se mandan — una etiqueta en blanco solo gasta tokens.
    """
    lineas = [f'<ficha_acc id="{ficha.pk}">']
    for nombre in CAMPOS_ENVIADOS:
        valor = (getattr(ficha, nombre, "") or "").strip()
        if not valor:
            continue
        pregunta = ficha._meta.get_field(nombre).verbose_name
        lineas.append(
            f"  <{nombre} pregunta={quoteattr(str(pregunta))}>{escape(valor)}</{nombre}>"
        )
    lineas.append("</ficha_acc>")
    return "\n".join(lineas)


def redactar(ficha) -> Redaccion:
    """Lee la ficha ACC y devuelve la medida propuesta. Lanza si algo impide continuar."""
    respuesta = openrouter.completar(
        [
            {"role": "system", "content": INSTRUCCIONES},
            {"role": "user", "content": entrada_ficha(ficha)[:MAXIMO_CARACTERES]},
        ],
        # Extraer campos de un formulario no mejora razonando y sí se paga. `None` no valdría: el
        # modelo por defecto razona salvo que se le diga que no.
        razonamiento=False,
        response_format={"type": "json_schema", "json_schema": _esquema()},
        # Cierra el fallo intermitente: OpenRouter enruta cada petición por separado y del mismo
        # modelo hay proveedores sin salida estructurada.
        extra_body={"provider": {"require_parameters": True}},
        etiqueta=f"medida desde ficha ACC #{ficha.pk}",
    )

    datos = salida_ia.interpretar_json(respuesta.texto)
    if not str(datos.get("titulo") or "").strip():
        raise ValueError(_MOTIVO_SIN_FICHA)

    return _normalizar(datos, modelo=respuesta.modelo, costo=respuesta.costo)


# --- Internos ---------------------------------------------------------------

_MOTIVO_SIN_FICHA = (
    "La respuesta no permitió identificar la experiencia. Puede que la ficha esté casi vacía o "
    "que sus respuestas no describan una práctica; revísala en «Medidas - Fichas ACC» y, si está "
    "bien, redacta la medida a mano."
)


def _normalizar(datos: dict, *, modelo: str, costo: float | None) -> Redaccion:
    from apps.medidas.models import Medida

    ambitos = {opcion for opcion, _ in Medida.Ambito.choices}
    resultados = {opcion for opcion, _ in Medida.Resultado.choices}

    ambito = str(datos.get("ambito") or "").strip().lower()
    resultado = str(datos.get("resultado") or "").strip().lower()

    claves = [
        str(palabra).strip()[:60]
        for palabra in (datos.get("palabras_clave") or [])
        if str(palabra).strip()
    ]

    avisos: list[str] = []
    fecha = _a_fecha(datos.get("fecha_implementacion"), avisos)

    return Redaccion(
        titulo=str(datos.get("titulo") or "").strip()[:200],
        resumen_corto=str(datos.get("resumen_corto") or "").strip()[:500],
        tipo_peligro=_resolver_peligro(datos.get("tipo_peligro"), avisos),
        # Sin repliegue inventado (ADR-D8): lo que no cuadra con el catálogo se deja vacío, que es
        # lo que hace que el editor lo vea y lo elija.
        ambito=ambito if ambito in ambitos else "",
        resultado=resultado if resultado in resultados else "",
        distrito=_resolver_distrito(datos.get("distrito"), datos.get("provincia"), avisos),
        comunidad=str(datos.get("comunidad") or "").strip()[:150],
        contenido=salida_ia.a_html(str(datos.get("contenido") or "").strip(), avisos),
        palabras_clave=claves[:8],
        actores=str(datos.get("actores") or "").strip()[:300],
        fecha_implementacion=fecha,
        costo_referencial=_a_decimal(datos.get("costo_referencial"), avisos),
        modelo=modelo,
        costo=costo,
        avisos=avisos,
    )


def _resolver_peligro(slug, avisos: list[str]):
    from apps.peligros.models import TipoPeligro

    slug = str(slug or "").strip()
    if not slug:
        return None
    peligro = TipoPeligro.objects.filter(slug=slug).first()
    if peligro is None:
        avisos.append(f"«{slug}» no está en el catálogo de peligros: elige el tipo a mano.")
    return peligro


def _resolver_distrito(nombre, provincia, avisos: list[str]):
    """El nombre solo no basta: en Perú los nombres de distrito se repiten entre provincias.

    Cero candidatos (la experiencia es de fuera de Cusco) o dos (homónimos sin provincia) dejan
    el campo vacío y lo dicen. Adivinar pondría la medida en el distrito equivocado del mapa.
    """
    from apps.territorio.models import Distrito
    from apps.territorio.utils import normalizar_nombre

    nombre = str(nombre or "").strip()
    if not nombre:
        return None

    candidatos = Distrito.objects.filter(nombre_normalizado=normalizar_nombre(nombre))
    if provincia and str(provincia).strip():
        candidatos = candidatos.filter(provincia__nombre__iexact=str(provincia).strip())

    encontrados = list(candidatos.select_related("provincia")[:2])
    if len(encontrados) == 1:
        return encontrados[0]

    avisos.append(
        f"No se pudo ubicar el distrito «{nombre}»"
        + (" (hay más de uno con ese nombre)" if encontrados else "")
        + ": elígelo a mano si corresponde a Cusco."
    )
    return None


def _a_fecha(valor, avisos: list[str]) -> date | None:
    """La fecha de inicio. ISO si viene completa; si no, el **primer año** que aparezca.

    **Sin repliegue a hoy.** A diferencia de `Norma.fecha`, este campo es nullable: poner la fecha
    de hoy sería un dato falso indistinguible de uno real, y el periodo de una experiencia es
    justo lo que alguien citaría en un informe.

    Lo del primer año no es una concesión teórica: pedida la fecha de inicio de «Enero de 2019 a
    diciembre de 2022», el modelo responde `"2019-2022"`. Tomar el 2019 es leer lo que la ficha
    dice, no adivinarlo; lo que sí sería adivinar es el mes, y por eso queda el aviso.
    """
    crudo = str(valor or "").strip()
    if not crudo:
        return None
    try:
        return date.fromisoformat(crudo[:10])
    except ValueError:
        pass

    # `19\d\d|20\d\d` y no `\d{4}`: sin el tope, un importe o un teléfono dentro de la
    # respuesta se convertiría en una fecha plausible y falsa.
    anio = re.search(r"\b(19\d\d|20\d\d)\b", crudo)
    if anio is None:
        return None
    avisos.append(
        f"La fecha de implementación se dedujo de «{crudo}»: quedó en el 1 de enero de "
        f"{anio.group(1)}, corrígela si conoces el mes."
    )
    return date(int(anio.group(1)), 1, 1)


#: Lo que descarta un monto entero: si aparece otra moneda, no se convierte (inventar un tipo de
#: cambio es la misma invención de cifras que fundó ADR-D4).
_OTRA_MONEDA = re.compile(r"(?i)\b(usd|eur|d[oó]lar|euro)|\$|€")
#: Lo que se puede quitar sin cambiar la cifra: la moneda local escrita de las formas de siempre.
_SOLES = re.compile(r"(?i)\bsoles?\b|\bpen\b|s/\.?|\bnuevos?\b")


def _a_decimal(valor, avisos: list[str]) -> Decimal | None:
    """Solo un monto en soles. **Nada de convertir monedas ni de redondear a ciegas.**

    Se limpia lo que no cambia la cifra —«S/», «soles», «PEN» y las comas de millar— porque es lo
    que devuelve el modelo de verdad («180,000 soles») y rechazarlo perdía un dato que la ficha
    sí daba. La coma es separador de millar y el punto decimal: es la convención peruana, y es
    también la única lectura compatible con `Decimal(12, 2)`.
    """
    crudo = str(valor or "").strip()
    if not crudo:
        return None
    if _OTRA_MONEDA.search(crudo):
        avisos.append(
            f"El costo «{crudo}» no está en soles y no se convierte: escríbelo a mano si "
            f"conoces el equivalente."
        )
        return None

    limpio = _SOLES.sub("", crudo).replace(",", "").replace(" ", "")
    try:
        monto = Decimal(limpio)
    except InvalidOperation:
        avisos.append(f"No se pudo leer el costo «{crudo}» como un monto en soles.")
        return None
    if monto < 0 or monto >= TOPE_COSTO:
        avisos.append(f"El costo «{crudo}» no cabe en el campo: escríbelo a mano si es correcto.")
        return None
    return monto.quantize(Decimal("0.01"))
