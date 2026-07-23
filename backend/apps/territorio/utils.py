import re
import unicodedata


def normalizar_nombre(nombre: str) -> str:
    """MAYÚSCULAS, sin tildes ni espacios repetidos — para casar nombres de
    distrito que llegan en Excel sin ubigeo."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", nombre or "") if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_tildes).strip().upper()
