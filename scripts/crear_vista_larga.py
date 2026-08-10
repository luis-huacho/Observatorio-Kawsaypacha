#!/usr/bin/env python3
"""Crea una vista que gira los ejercicios de columnas a filas.

El comparativo del MEF viene ancho: una fila por combinación presupuestal con los cinco
ejercicios abiertos en 35 columnas (7 métricas × 5 años). Para revisar la serie eso obliga
a repetir cada métrica en el SELECT en vez de agrupar por año. La vista devuelve las mismas
dimensiones más `EJERCICIO` y las 7 métricas sin sufijo, así que `GROUP BY EJERCICIO` funciona.

Es una vista, no una tabla: no ocupa disco y se calcula al consultar. Como la base es
desechable y se regenera desde el CSV, este script es lo que la reconstruye.

Por defecto se descartan los cortes año-fila **enteramente en cero**: el comparativo rellena
con ceros los años en que la combinación no existía, y en el programa 0068 eso es el 71 % de
los cortes. Con --incluir-vacios se conservan.

Ejemplo:

    python3 scripts/crear_vista_larga.py inversion_cusco.sqlite3 --programa 0068
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys

from csv_a_sqlite import MONETARIA, citar

SUFIJO_ANIO = re.compile(r"_(\d{4})$")


def analizar_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crea una vista larga (un registro por combinación y ejercicio) sobre la tabla ancha."
    )
    parser.add_argument("base", help="Archivo .sqlite3 con la tabla ancha.")
    parser.add_argument("--tabla", default="gastos", help="Tabla de origen (por defecto: gastos).")
    parser.add_argument(
        "--programa",
        help="Categoría presupuestal a la que se limita la vista (PROGRAMA_PPTO), p. ej. 0068. "
        "Sin este argumento la vista cubre toda la tabla.",
    )
    parser.add_argument("--vista", help="Nombre de la vista (por defecto se deriva de tabla y programa).")
    parser.add_argument(
        "--incluir-vacios",
        action="store_true",
        help="Conservar los cortes año-fila con las 7 métricas en cero.",
    )
    return parser.parse_args()


def clasificar(columnas: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Separa dimensiones de métricas y devuelve (dimensiones, metricas, ejercicios)."""
    dimensiones, metricas, ejercicios = [], [], []
    for columna in columnas:
        if not MONETARIA.match(columna):
            dimensiones.append(columna)
            continue
        base, anio = SUFIJO_ANIO.split(columna)[:2]
        if base not in metricas:
            metricas.append(base)
        if anio not in ejercicios:
            ejercicios.append(anio)
    return dimensiones, metricas, sorted(ejercicios)


def main() -> None:
    args = analizar_argumentos()
    conexion = sqlite3.connect(args.base)

    columnas = [fila[1] for fila in conexion.execute(f"PRAGMA table_info({citar(args.tabla)})")]
    if not columnas:
        raise SystemExit(f"La tabla {args.tabla!r} no existe en {args.base}.")

    dimensiones, metricas, ejercicios = clasificar(columnas)
    faltantes = [
        f"{metrica}_{anio}"
        for anio in ejercicios
        for metrica in metricas
        if f"{metrica}_{anio}" not in columnas
    ]
    if faltantes:
        raise SystemExit("Faltan columnas para completar la serie: " + ", ".join(faltantes))

    condiciones = []
    if args.programa is not None:
        if not args.programa.strip().isalnum():
            raise SystemExit(f"--programa {args.programa!r}: se esperaba un código alfanumérico.")
        if "PROGRAMA_PPTO" not in dimensiones:
            raise SystemExit("La tabla no tiene columna PROGRAMA_PPTO; no se puede filtrar por programa.")
        condiciones.append(f"{citar('PROGRAMA_PPTO')} = '{args.programa}'")

    vista = args.vista or "_".join(filter(None, [args.tabla, args.programa, "largo"]))

    seleccion = ", ".join(citar(dimension) for dimension in dimensiones)
    ramas = []
    for anio in ejercicios:
        proyeccion = ", ".join(
            f"{citar(metrica + '_' + anio)} AS {citar(metrica)}" for metrica in metricas
        )
        donde = list(condiciones)
        if not args.incluir_vacios:
            vacio = " OR ".join(f"{citar(metrica + '_' + anio)} <> 0" for metrica in metricas)
            donde.append(f"({vacio})")
        rama = f"SELECT {seleccion}, {anio} AS {citar('EJERCICIO')}, {proyeccion} FROM {citar(args.tabla)}"
        if donde:
            rama += " WHERE " + " AND ".join(donde)
        ramas.append(rama)

    conexion.execute(f"DROP VIEW IF EXISTS {citar(vista)}")
    conexion.execute(f"CREATE VIEW {citar(vista)} AS\n" + "\nUNION ALL\n".join(ramas))
    conexion.commit()

    filas = conexion.execute(f"SELECT COUNT(*) FROM {citar(vista)}").fetchone()[0]
    conexion.close()

    print(
        f"Vista {vista}: {len(dimensiones)} dimensiones + EJERCICIO + {len(metricas)} métricas "
        f"({', '.join(metricas)}).\n"
        f"Ejercicios {ejercicios[0]}–{ejercicios[-1]}"
        + (f", limitada a PROGRAMA_PPTO = {args.programa}" if args.programa else "")
        + (", con los cortes vacíos" if args.incluir_vacios else ", sin los cortes todo-cero")
        + f".\n{filas:,} filas.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
