#!/usr/bin/env python3
"""Extrae de un volcado de gastos del MEF las filas de un departamento, sin transformarlas.

El volcado nacional (`comparativo_gastos_2022_2026.csv`) pesa ~9 GB y trae 88 columnas.
Este script escribe un subconjunto con las mismas columnas y las mismas filas textuales:
copia cada línea que coincide **byte a byte**, así que el resultado conserva el BOM, las
comillas y los finales de línea CRLF del original y puede tratarse como el mismo CSV.

Coincide una fila si CUALQUIERA de las columnas indicadas es igual al departamento
buscado. Por defecto se miran las dos geografías del archivo: dónde está la unidad que
gasta (DEPARTAMENTO_EJECUTORA_NOMBRE) y a qué departamento se dirige la meta
(DEPARTAMENTO_META_NOMBRE).

Ejemplo:

    python3 scripts/get_data_cusco.py \\
        data/inversion/comparativo_gastos_2022_2026.csv \\
        data/inversion/comparativo_cusco_gastos_2022_2026.csv
"""

from __future__ import annotations

import argparse
import sys

BOM = b"\xef\xbb\xbf"
SEPARADOR = b'","'
COLUMNAS_POR_DEFECTO = ("DEPARTAMENTO_EJECUTORA_NOMBRE", "DEPARTAMENTO_META_NOMBRE")
BUFFER = 1024 * 1024
PASO_PROGRESO = 1_000_000


def pelar(campo: bytes) -> bytes:
    """Quita las comillas de los extremos.

    Al partir por `","` solo el primer y el último campo conservan su comilla; los de en
    medio salen limpios. Se pela igualmente para que --columnas acepte cualquier columna.
    """
    if campo.startswith(b'"'):
        campo = campo[1:]
    if campo.endswith(b'"'):
        campo = campo[:-1]
    return campo


def leer_cabecera(entrada) -> tuple[bytes, list[bytes], bytes]:
    """Devuelve (línea cruda, nombres de columna, terminador de línea)."""
    cruda = entrada.readline()
    if not cruda:
        raise SystemExit("El archivo de entrada está vacío.")

    terminador = b"\r\n" if cruda.endswith(b"\r\n") else b"\n"
    contenido = cruda[: -len(terminador)]
    if contenido.startswith(BOM):
        contenido = contenido[len(BOM) :]

    nombres = [pelar(campo) for campo in contenido.split(SEPARADOR)]
    return cruda, nombres, terminador


def resolver_indices(nombres: list[bytes], pedidas: list[str]) -> list[int]:
    indices = []
    for pedida in pedidas:
        clave = pedida.encode("utf-8")
        if clave not in nombres:
            disponibles = ", ".join(nombre.decode("utf-8", "replace") for nombre in nombres)
            raise SystemExit(
                f"La columna {pedida!r} no está en la cabecera.\nColumnas disponibles: {disponibles}"
            )
        indices.append(nombres.index(clave))
    return indices


def analizar_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copia a un archivo nuevo las filas de un departamento, sin transformarlas. "
            "La cabecera y cada fila se escriben tal cual vienen del original."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("entrada", help="CSV de origen (volcado nacional del MEF).")
    parser.add_argument("salida", help="CSV a generar con el subconjunto.")
    parser.add_argument(
        "--departamento",
        default="CUSCO",
        help=(
            "Valor a buscar, por defecto CUSCO. La comparación es exacta y distingue "
            "mayúsculas: se escribe como aparece en el archivo (mayúsculas, sin tildes)."
        ),
    )
    parser.add_argument(
        "--columnas",
        nargs="+",
        default=list(COLUMNAS_POR_DEFECTO),
        metavar="COLUMNA",
        help=(
            "Columnas donde buscar el departamento, por nombre de cabecera. La fila entra "
            "si coincide alguna (OR). Por defecto: " + " ".join(COLUMNAS_POR_DEFECTO) + "."
        ),
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        metavar="N",
        help="Procesar solo las primeras N filas de datos. Para pruebas rápidas.",
    )
    return parser.parse_args()


def main() -> None:
    args = analizar_argumentos()
    buscado = args.departamento.encode("utf-8")
    # Prefiltro: si un campo vale CUSCO, la línea contiene `"CUSCO"`. Es un superconjunto
    # estricto del criterio, así que descarta la mayoría de las líneas sin poder perder
    # ninguna coincidencia, y evita partir en 88 campos las que no vienen al caso.
    aguja = b'"' + buscado + b'"'

    with open(args.entrada, "rb", buffering=BUFFER) as entrada:
        cruda, nombres, terminador = leer_cabecera(entrada)
        indices = resolver_indices(nombres, args.columnas)
        n_columnas = len(nombres)
        largo_terminador = len(terminador)

        print(
            f"Columnas: {n_columnas}. Buscando {args.departamento!r} en "
            + ", ".join(args.columnas),
            file=sys.stderr,
        )

        leidas = candidatas = coincidentes = 0
        por_columna = [0] * len(indices)

        with open(args.salida, "wb", buffering=BUFFER) as salida:
            salida.write(cruda)  # cabecera verbatim, con BOM y terminador originales

            for cruda_fila in entrada:
                leidas += 1
                if leidas % PASO_PROGRESO == 0:
                    print(
                        f"  {leidas:,} filas leídas, {coincidentes:,} coincidentes…",
                        file=sys.stderr,
                    )

                if aguja in cruda_fila:
                    candidatas += 1
                    campos = cruda_fila[:-largo_terminador].split(SEPARADOR)
                    if len(campos) != n_columnas:
                        raise SystemExit(
                            f"Fila {leidas + 1}: {len(campos)} campos en vez de {n_columnas}. "
                            "El archivo ya no cumple «un registro = una línea»; el filtro por "
                            "líneas dejaría de ser correcto."
                        )
                    acierto = False
                    for posicion, indice in enumerate(indices):
                        if pelar(campos[indice]) == buscado:
                            por_columna[posicion] += 1
                            acierto = True
                    if acierto:
                        coincidentes += 1
                        salida.write(cruda_fila)

                if args.limite and leidas >= args.limite:
                    break

            escritos = salida.tell()

    print(
        f"\nFilas leídas:      {leidas:,}\n"
        f"Candidatas:        {candidatas:,} (contenían {aguja.decode()})\n"
        f"Coincidentes:      {coincidentes:,}",
        file=sys.stderr,
    )
    for columna, cuenta in zip(args.columnas, por_columna):
        print(f"  por {columna}: {cuenta:,}", file=sys.stderr)
    print(
        f"Escrito en {args.salida}: {coincidentes + 1:,} líneas, {escritos:,} bytes.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
