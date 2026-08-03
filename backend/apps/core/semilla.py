"""Carga de datos semilla desde YAML.

No se usa `loaddata` por dos razones, y la segunda es la importante:

1. `loaddata` hace inserciones *raw*, que se saltan `auto_now_add`/`auto_now` y chocan con los
   `NOT NULL` de `TimeStampedMixin`. Se puede sortear poniendo las fechas en el YAML, pero es
   ruido en cada registro.
2. **`loaddata` pisa por pk.** El runbook corre el seed en cada despliegue, y estos registros
   —menú, textos, configuración, capas— son justo los que PREDES edita desde el admin. Un
   `loaddata` en el despliegue le devolvería sus textos al valor de fábrica sin avisar.

Así que la semántica por defecto es *crear lo que falta y no tocar lo que ya existe*.
"""
from pathlib import Path

import yaml


def leer(ruta) -> dict:
    with Path(ruta).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def sembrar(modelo, registros, claves, actualizar: bool = False) -> tuple[int, int]:
    """Crea los registros que falten, identificándolos por `claves`.

    `claves` es el nombre de un campo o una lista de campos que, juntos, identifican la fila
    en el YAML (no hace falta que sean una unique constraint de la base).

    Devuelve (creados, existentes). Con `actualizar=True` sobreescribe también los que ya
    estaban — solo para catálogos que son código, nunca para contenido que el cliente edita.
    """
    if isinstance(claves, str):
        claves = [claves]

    creados = existentes = 0
    for fila in registros or []:
        datos = dict(fila)
        filtro = {k: datos.pop(k) for k in claves}
        objeto = modelo.objects.filter(**filtro).first()
        if objeto is None:
            modelo.objects.create(**filtro, **datos)
            creados += 1
        else:
            existentes += 1
            if actualizar:
                for campo, valor in datos.items():
                    setattr(objeto, campo, valor)
                objeto.save()
    return creados, existentes


def sembrar_singleton(modelo, campos: dict) -> bool:
    """Crea el registro único si todavía no hay ninguno. Devuelve True si lo creó."""
    if modelo.objects.exists():
        return False
    modelo.objects.create(**campos)
    return True
