from rest_framework.throttling import AnonRateThrottle


class DescargaThrottle(AnonRateThrottle):
    """Exports Excel y ayudas memoria PDF: 30/hora (spec 02).

    Una descarga cuesta órdenes de magnitud más que una lectura —abre el Excel completo o
    lanza un navegador headless—, así que un bucle de descargas tumbaría el worker mucho
    antes que el API. Va con su propia cubeta para no castigar la navegación normal.
    """

    scope = "descarga"


class BeaconThrottle(AnonRateThrottle):
    """Métricas por `sendBeacon`: 60/minuto por IP.

    Es el único endpoint de escritura público. El límite acota el ruido de un cliente roto o
    de alguien inflando las cifras a mano, sin llegar a estorbar a un usuario real.
    """

    scope = "beacon"
