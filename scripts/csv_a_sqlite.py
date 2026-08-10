#!/usr/bin/env python3
"""Carga un volcado de gastos del MEF en una base SQLite para poder consultarlo con SQL.

El CSV recortado por `get_data_cusco.py` es fiel al original, pero no es explorable: cada
pregunta obliga a barrer cientos de MB de texto. Esta base es una herramienta de trabajo
—desechable, se regenera desde el CSV— y no sustituye a `DatasetUpload`, que sigue siendo
la única vía de importación real de la aplicación.

Las 35 columnas de importes (7 métricas × 5 ejercicios) se guardan como REAL para poder
sumarlas y ordenarlas directamente. El resto va TEXT: los códigos del MEF llevan ceros a la
izquierda (`08`, `0068`, `00003`) que como número se perderían.

Ejemplo:

    python3 scripts/csv_a_sqlite.py \\
        data/inversion/comparativo_cusco_gastos_2022_2026.csv \\
        inversion_cusco.sqlite3
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

# Columnas por las que se filtra o se agrupa al revisar. Se indexan después de la carga.
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

        es_real = [bool(MONETARIA.match(nombre)) for nombre in columnas]
        n_columnas = len(columnas)
        print(
            f"{n_columnas} columnas: {sum(es_real)} REAL (importes), "
            f"{n_columnas - sum(es_real)} TEXT (dimensiones).",
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
            f"{citar(nombre)} {'REAL' if real else 'TEXT'}"
            for nombre, real in zip(columnas, es_real)
        )
        conexion.execute(f"CREATE TABLE {citar(args.tabla)} ({definicion})")

        insercion = (
            f"INSERT INTO {citar(args.tabla)} VALUES ({', '.join('?' * n_columnas)})"
        )
        indices_reales = [i for i, real in enumerate(es_real) if real]

        filas = 0
        lote: list[list] = []
        conexion.execute("BEGIN")
        for cruda in lector:
            filas += 1
            if len(cruda) != n_columnas:
                raise SystemExit(
                    f"Fila {filas + 1}: {len(cruda)} campos en vez de {n_columnas}."
                )
            for i in indices_reales:
                try:
                    cruda[i] = float(cruda[i])
                except ValueError:
                    raise SystemExit(
                        f"Fila {filas + 1}, columna {columnas[i]}: "
                        f"{cruda[i]!r} no es un número."
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
    for columna in INDICES:
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
