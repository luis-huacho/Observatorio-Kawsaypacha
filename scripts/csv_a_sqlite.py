#!/usr/bin/env python3
"""Carga un CSV de gastos en una base SQLite para poder consultarlo con SQL.

Los CSV que produce este proyecto son fieles a su origen, pero no son explorables: cada
pregunta obliga a barrer el archivo entero. Esta base es una herramienta de trabajo
—desechable, se regenera desde el CSV— y no sustituye a `DatasetUpload`, que sigue siendo
la única vía de importación real de la aplicación.

**El tipo de cada columna se declara, nunca se deduce del contenido.** Los códigos del MEF
llevan ceros a la izquierda (`08`, `0068`, `006`) que como número se perderían, y parsean
como número igual de bien que un importe. Por defecto solo van a REAL las columnas que
llevan el ejercicio en el nombre (`PIM_2024`); para las demás están `--reales` y `--enteros`.

Ejemplos:

    # volcado del MEF: las 35 columnas de importe se detectan solas
    python3 scripts/csv_a_sqlite.py \\
        data/inversion/comparativo_cusco_gastos_2022_2025.csv \\
        inversion_cusco.sqlite3

    # consolidado en formato largo: las métricas no llevan año, hay que declararlas
    python3 scripts/csv_a_sqlite.py \\
        data/inversion/pp0068_cusco_2022_2026_largo.csv pp0068_cusco.sqlite3 \\
        --tabla pp0068 --reales PIA PIM DEVENGADO --enteros EJERCICIO EN_BASE_2026 \\
        --indices EJERCICIO ENTIDAD_CODIGO PROVINCIA DISTRITO PRODUCTO_PROYECTO TIPO
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
import sys

# PIA_2024, DEVENGADO_2026, COMPROMETIDO_ANUAL_2023… El año al final es lo que las separa
# de las dimensiones; ninguna columna de dimensión termina en _<4 dígitos>.
MONETARIA = re.compile(r"^(PIA|PIM|CERTIFICADO|COMPROMETIDO_ANUAL|COMPROMETIDO|DEVENGADO|GIRADO)_\d{4}$")

# Índices por defecto, pensados para el volcado del MEF: las columnas por las que se filtra o
# se agrupa al revisarlo. Se crean después de la carga y se sustituyen con --indices.
INDICES = (
    "NIVEL_GOBIERNO",
    "DEPARTAMENTO_EJECUTORA_NOMBRE",
    "PROVINCIA_EJECUTORA_NOMBRE",
    "DISTRITO_EJECUTORA_NOMBRE",
    "EJECUTORA_NOMBRE",
    "FUNCION_NOMBRE",
    "TIPO_ACT_PROY_NOMBRE",
    "DEPARTAMENTO_META_NOMBRE",
    "FUENTE_FINANCIAMIENTO_NOMBRE",
)

PASO_PROGRESO = 100_000


def citar(identificador: str) -> str:
    """Cita un nombre de tabla o columna para el DDL."""
    return '"' + identificador.replace('"', '""') + '"'


def analizar_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Carga un CSV de gastos del MEF en SQLite. Los importes van REAL y las "
            "dimensiones TEXT, para no perder los ceros a la izquierda de los códigos."
        )
    )
    parser.add_argument("entrada", help="CSV de origen.")
    parser.add_argument("salida", help="Archivo .sqlite3 a crear.")
    parser.add_argument("--tabla", default="gastos", help="Nombre de la tabla (por defecto: gastos).")
    parser.add_argument(
        "--reales",
        nargs="+",
        default=[],
        metavar="COLUMNA",
        help=(
            "Columnas a guardar como REAL, además de las que llevan el ejercicio en el nombre "
            "(PIM_2024). Hace falta cuando las métricas no lo llevan, como en el consolidado."
        ),
    )
    parser.add_argument(
        "--enteros",
        nargs="+",
        default=[],
        metavar="COLUMNA",
        help=(
            "Columnas a guardar como INTEGER. Importa para las banderas: si EN_BASE_2026 queda "
            "como texto, `WHERE EN_BASE_2026 = 1` no devuelve nada y no avisa."
        ),
    )
    parser.add_argument(
        "--indices",
        nargs="+",
        default=list(INDICES),
        metavar="COLUMNA",
        help="Columnas a indexar. Por defecto, las del volcado del MEF.",
    )
    parser.add_argument(
        "--rehacer",
        action="store_true",
        help="Borrar la base si ya existe. Sin esta bandera el script aborta antes de pisarla.",
    )
    parser.add_argument(
        "--lote",
        type=int,
        default=50_000,
        metavar="N",
        help="Filas por executemany (por defecto: 50000).",
    )
    return parser.parse_args()


def resolver_tipos(columnas: list[str], reales: list[str], enteros: list[str]) -> list[str]:
    """Tipo SQLite de cada columna: TEXT salvo lo que se declare numérico.

    Nunca se deduce del contenido. `ENTIDAD_CODIGO` vale `006` y `PRODUCTO_PROYECTO` vale
    `3000001`: los dos parsean como número y perderían el cero a la izquierda o dejarían de
    casar con los catálogos del MEF.
    """
    for nombre in [*reales, *enteros]:
        if nombre not in columnas:
            raise SystemExit(
                f"La columna {nombre!r} no está en la cabecera.\n"
                "Columnas disponibles: " + ", ".join(columnas)
            )
    repetidas = set(reales) & set(enteros)
    if repetidas:
        raise SystemExit("Columnas declaradas a la vez REAL e INTEGER: " + ", ".join(sorted(repetidas)))

    tipos = []
    for nombre in columnas:
        if nombre in enteros:
            tipos.append("INTEGER")
        elif nombre in reales or MONETARIA.match(nombre):
            tipos.append("REAL")
        else:
            tipos.append("TEXT")
    return tipos


def preparar_salida(ruta: str, rehacer: bool) -> None:
    if not os.path.exists(ruta):
        return
    if not rehacer:
        raise SystemExit(f"{ruta} ya existe. Usa --rehacer para reemplazarla.")
    os.remove(ruta)
    for sufijo in ("-wal", "-shm"):
        if os.path.exists(ruta + sufijo):
            os.remove(ruta + sufijo)


def main() -> None:
    args = analizar_argumentos()
    preparar_salida(args.salida, args.rehacer)

    with open(args.entrada, newline="", encoding="utf-8-sig") as f:
        lector = csv.reader(f)
        try:
            columnas = next(lector)
        except StopIteration:
            raise SystemExit("El archivo de entrada está vacío.")

        tipos = resolver_tipos(columnas, args.reales, args.enteros)
        n_columnas = len(columnas)
        print(
            f"{n_columnas} columnas: "
            + ", ".join(
                f"{tipos.count(t)} {t}" for t in ("REAL", "INTEGER", "TEXT") if tipos.count(t)
            )
            + ".",
            file=sys.stderr,
        )

        conexion = sqlite3.connect(args.salida)
        # Base desechable: sin journal ni fsync la carga va mucho más rápida y no hay nada
        # que proteger de un corte, porque se regenera desde el CSV.
        conexion.execute("PRAGMA journal_mode = OFF")
        conexion.execute("PRAGMA synchronous = OFF")
        conexion.execute("PRAGMA temp_store = MEMORY")
        conexion.execute("PRAGMA cache_size = -200000")

        definicion = ", ".join(
            f"{citar(nombre)} {tipo}" for nombre, tipo in zip(columnas, tipos)
        )
        conexion.execute(f"CREATE TABLE {citar(args.tabla)} ({definicion})")

        insercion = (
            f"INSERT INTO {citar(args.tabla)} VALUES ({', '.join('?' * n_columnas)})"
        )
        conversiones = [
            (i, float if tipo == "REAL" else int)
            for i, tipo in enumerate(tipos)
            if tipo != "TEXT"
        ]

        filas = 0
        lote: list[list] = []
        conexion.execute("BEGIN")
        for cruda in lector:
            filas += 1
            if len(cruda) != n_columnas:
                raise SystemExit(
                    f"Fila {filas + 1}: {len(cruda)} campos en vez de {n_columnas}."
                )
            for i, convertir in conversiones:
                try:
                    cruda[i] = convertir(cruda[i])
                except ValueError:
                    raise SystemExit(
                        f"Fila {filas + 1}, columna {columnas[i]}: "
                        f"{cruda[i]!r} no es un {tipos[i]}."
                    )
            lote.append(cruda)

            if len(lote) >= args.lote:
                conexion.executemany(insercion, lote)
                lote.clear()
                if filas % PASO_PROGRESO < args.lote:
                    print(f"  {filas:,} filas cargadas…", file=sys.stderr)

        if lote:
            conexion.executemany(insercion, lote)
        conexion.commit()

    print(f"{filas:,} filas cargadas. Creando índices…", file=sys.stderr)
    for columna in args.indices:
        if columna not in columnas:
            print(f"  (aviso) sin índice: {columna} no está en el CSV", file=sys.stderr)
            continue
        conexion.execute(
            f"CREATE INDEX {citar('ix_' + args.tabla + '_' + columna.lower())} "
            f"ON {citar(args.tabla)} ({citar(columna)})"
        )
    conexion.execute("ANALYZE")
    conexion.commit()
    conexion.close()

    tamano = os.path.getsize(args.salida)
    print(
        f"\nBase {args.salida}: tabla {args.tabla}, {filas:,} filas, "
        f"{tamano / 1024 / 1024:,.0f} MB.\n"
        f"Explorar con:  sqlite3 {args.salida}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
