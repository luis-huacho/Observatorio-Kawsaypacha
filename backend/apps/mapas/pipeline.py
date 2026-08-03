"""Pipeline de tiles (spec 05). Implementación en la fase de mapas.

Se deja el contrato explícito para que el admin y el seed fallen con un mensaje entendible en
lugar de con un ImportError en el log del worker.
"""


def generar_capa(capa_id: int) -> str:
    raise NotImplementedError(
        "El pipeline de tiles de capas todavía no está implementado en esta fase."
    )


def generar_ccpp() -> str:
    raise NotImplementedError(
        "El pipeline de tiles de centros poblados todavía no está implementado en esta fase."
    )
