#!/usr/bin/env python3
"""Emite los centros poblados como GeoJSONSeq en formato ANCHO, listo para tippecanoe.

Formato ancho = una propiedad `nivel_<slug>` por peligro, más `nivel_max`. Eso permite que el
visor cambie de peligro y de nivel mínimo con expresiones de MapLibre sobre el tile ya
descargado, sin volver a pedir nada al servidor.

Lee los JSON que produce xlsx_to_json.py y escribe una línea por Feature en stdout:
  python3 prototype/scripts/ccpp_to_geojsonseq.py > /tmp/ccpp.jsonl
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "prototype" / "public" / "data"

# Mismo orden y slugs que PELIGROS en prototype/src/lib/types.ts.
SLUGS = [
    "sismo", "heladas", "bajas_temperaturas", "friaje", "sequia",
    "lluvias_intensas", "inundacion", "incendios_forestales", "movimientos_en_masa",
]


def main() -> None:
    ccpp = json.loads((DATA / "ccpp.json").read_text(encoding="utf-8"))
    peligros = json.loads((DATA / "peligros.json").read_text(encoding="utf-8"))

    # codigo -> {slug: nivel}. Si un CCPP tuviera dos filas del mismo peligro, gana la mayor.
    niveles: dict[str, dict[str, int]] = {}
    for p in peligros:
        fila = niveles.setdefault(p["codigo_ccpp"], {})
        slug = p["peligro_slug"]
        if p["nivel"] > fila.get(slug, 0):
            fila[slug] = p["nivel"]

    emitidos = 0
    sin_coords = 0

    for c in ccpp:
        if c["lat"] is None or c["lon"] is None:
            sin_coords += 1
            continue

        fila = niveles.get(c["codigo"], {})
        props = {
            "codigo": c["codigo"],
            "nombre": c["nombre"],
            "categoria": c["categoria"],
            "distrito": c["distrito"],
            "provincia": c["provincia"],
            "ubigeo_distrito": c["ubigeo_distrito"],
            "poblacion": c["poblacion"],
            "altitud": c["altitud"],
        }
        # Solo se escriben los peligros presentes: tippecanoe no guarda las claves ausentes y
        # el tile queda mucho más liviano (5,730 de 8,968 CCPP no tienen ninguna clasificación).
        for slug in SLUGS:
            if slug in fila:
                props[f"nivel_{slug}"] = fila[slug]
        props["nivel_max"] = max(fila.values()) if fila else 0

        sys.stdout.write(json.dumps({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
            "properties": props,
        }, ensure_ascii=False) + "\n")
        emitidos += 1

    con_dato = sum(1 for c in ccpp if niveles.get(c["codigo"]))
    print(
        f"{emitidos} features emitidas ({con_dato} con al menos un peligro clasificado)"
        + (f", {sin_coords} sin coordenadas" if sin_coords else ""),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
