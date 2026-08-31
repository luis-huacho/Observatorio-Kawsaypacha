"""Lo que cada gráfico de Inversión DICE, en una frase.

Un gráfico se deja leer pero no concluye: la conclusión la tiene que sacar quien mira. La
ventana la usan autoridades, periodistas y universidades, y lo que esa gente necesita es la
frase que se puede copiar.

**Se redacta aquí, en un solo sitio, y viaja en el payload.** Es la misma decisión de ADR-D6
—el mapa manda `no_ubicado` con «su motivo ya redactado», porque la advertencia viaja con el
dato y no con la interfaz— y el mismo argumento del encabezado de `consultas.py`: lo leen la
SPA y el PDF, y que cada uno redacte por su cuenta es la forma segura de que un día no digan lo
mismo. La SPA imprime la cadena del payload; el PDF llama a estas funciones directamente.

El registro es el de las `.declaracion` del reporte: sujeto = la cifra, presente de indicativo,
tercera persona, sin adjetivos valorativos. **Sin color**: en la SPA `Delta` colorea porque
compara dos ejercicios que alguien eligió, pero aquí más presupuesto no es de suyo una buena
noticia y teñirlo de verde sería opinar por el lector.

La palabra «cerrado» no aparece —es jerga contable, y hay una prueba e2e que lo fija—: un
ejercicio terminado es «completo».

**Los formateadores entran por parámetro** porque los dos medios no escriben igual: la SPA usa
`Intl` (`53%`, sin espacio) y el PDF sus filtros (`53.0 %`, con espacio). Lo que no se duplica
es la frase; la tipografía la pone cada uno.
"""


def soles_web(valor) -> str:
    """`S/ 54,591,255` — el mismo formato que `formatSoles` del frontend."""
    return f"S/ {float(valor):,.0f}"


def pct_web(valor) -> str:
    """`53%`, `97.7%`, `1,272.7%` — el mismo que `formatPct` (un decimal como máximo)."""
    texto = f"{float(valor) * 100:,.1f}"
    return f"{texto[:-2] if texto.endswith('.0') else texto}%"


def _variacion(desde, hasta, soles, pct) -> str | None:
    """«subió S/ X (Y %)», o `None` si no hay base con la que comparar."""
    if not desde:
        return None
    delta = hasta - desde
    if delta == 0:
        return "se mantuvo igual"
    verbo = "subió" if delta > 0 else "bajó"
    return f"{verbo} {soles(abs(delta))} ({pct(abs(delta / desde))})"


def _mes_del_corte(punto) -> str:
    """«junio de 2026» ⇒ «junio»."""
    return (punto.get("corte_legible") or "").split(" de ")[0]


def ejecucion(agregados: dict, corte: str = "", soles=soles_web, pct=pct_web) -> str | None:
    """Del PIA al PIM y del PIM al devengado: lo que el primer gráfico enseña sin decirlo."""
    if not agregados.get("pim"):
        return None
    partes = []
    if agregados.get("pia"):
        variacion = agregados["variacion_pia_pim"]
        signo = "creció" if variacion >= 0 else "se redujo en"
        partes.append(
            f"El presupuesto {signo} {soles(abs(variacion))} "
            f"({pct(abs(variacion / agregados['pia']))}) entre lo aprobado al abrir el año y lo "
            f"vigente hoy."
        )
    if agregados.get("pct_ejecucion") is not None:
        cuando = f"Al corte de {corte} se" if corte else "Se"
        partes.append(
            f"{cuando} ha devengado el {pct(agregados['pct_ejecucion'])} y quedan "
            f"{soles(agregados['saldo'])} por ejecutar."
        )
    return " ".join(partes) or None


def procesos(lista: list[dict], sin_clasificar: dict, soles=soles_web, pct=pct_web) -> str | None:
    """Dónde se concentra el dinero entre los procesos de la GRD, y cuál se queda en cero."""
    con_pim = [p for p in lista if p["pim"] > 0]
    if not con_pim:
        return None
    mayor = max(con_pim, key=lambda p: p["pim"])

    cuanto = "la mayor parte" if mayor["pct"] is None else f"el {pct(mayor['pct'])}"
    partes = [f"{mayor['nombre']} concentra {cuanto} del presupuesto vigente ({soles(mayor['pim'])})."]

    # Un proceso en cero es un hallazgo, no un hueco del gráfico: la barra vacía no se explica
    # sola, y en este programa «Rehabilitación» lleva cinco ejercicios sin un sol.
    en_cero = [p["nombre"] for p in lista if p["pim"] == 0]
    if len(en_cero) == 1:
        partes.append(f"{en_cero[0]} no tiene presupuesto en este ejercicio.")
    elif en_cero:
        partes.append(
            f"{', '.join(en_cero[:-1])} y {en_cero[-1]} no tienen presupuesto en este ejercicio."
        )

    # Es la medida de lo que le falta al catálogo. Se declara en vez de repartirse entre los
    # demás procesos, que es lo que la haría desaparecer.
    if sin_clasificar.get("pim", 0) > 0:
        partes.append(
            f"{soles(sin_clasificar['pim'])} cuelgan de códigos que el catálogo aún no imputa a "
            f"ningún proceso."
        )
    return " ".join(partes)


def tendencia(serie: list[dict], soles=soles_web, pct=pct_web) -> str | None:
    """La tendencia, comparando **los dos últimos ejercicios completos**.

    Comparar el año en curso con el anterior daría un «el devengado bajó 59 %» que no mide una
    caída: mide medio año contra un año entero. El corte parcial se nombra aparte y sin número
    de variación, que es la única forma de que la frase no tenga que desmentirse a renglón
    seguido.
    """
    completos = [t for t in serie if not t["es_parcial"]]
    parciales = [t for t in serie if t["es_parcial"]]
    partes = []

    if len(completos) >= 2:
        previo, ultimo = completos[-2:]
        pim = _variacion(previo["pim"], ultimo["pim"], soles, pct)
        devengado = _variacion(previo["devengado"], ultimo["devengado"], soles, pct)
        if pim and devengado:
            partes.append(
                f"Entre {previo['anio']} y {ultimo['anio']}, los dos últimos ejercicios "
                f"completos, el presupuesto vigente {pim} y el gasto ejecutado {devengado}."
            )

    for parcial in parciales:
        partes.append(
            f"El ejercicio {parcial['anio']} va al corte de {_mes_del_corte(parcial)} y no se "
            f"compara con ellos."
        )
    return " ".join(partes) or None


def proyectos(bloque: dict, soles=soles_web, pct=pct_web) -> str | None:
    """Cuántas municipalidades tienen obra, y en cuántas manos está el dinero.

    Es la frase que corrige la lectura que fundó este bloque: el porcentaje en proyectos parece
    alto y se atribuye al Gobierno Regional, que **no está en este ámbito**. Lo que lo explica
    es que casi ninguna municipalidad tiene proyectos y unas pocas obras se llevan casi todo.
    """
    con, de, entidades = bloque["con_proyectos"], bloque["de"], bloque["entidades"]
    if not de:
        return None
    if not con:
        return (
            "Ninguna municipalidad del ámbito tiene presupuesto en proyectos de inversión: todo "
            "el programa está en actividades."
        )

    partes = [
        f"{con} de las {de} municipalidades del ámbito tienen presupuesto en proyectos de "
        f"inversión."
    ]

    # Cuántas hacen falta para llegar al 80 %: es la medida de concentración que se entiende sin
    # saber estadística, y la que convierte «parece mucho dinero» en «son estas obras».
    #
    # Solo se declara si esas pocas son **una minoría**. Con un reparto plano —cinco iguales—
    # cuatro suman el 80 % por pura aritmética, y decir «las 4 primeras concentran el 80 %»
    # haría sonar concentrado justo lo que está repartido. Es lo contrario de lo que la frase
    # viene a contar, y no falla a la vista: la cifra es correcta y la lectura, falsa.
    if con > 1 and bloque["pim"] > 0:
        acumulado = 0.0
        cuantas = 0
        for entidad in entidades:
            acumulado += entidad["pim_proyectos"]
            cuantas += 1
            if acumulado / bloque["pim"] >= 0.8:
                break
        if cuantas <= con / 2:
            # Con una sola se la nombra en vez de contarla: «Las 1 primeras» no es castellano, y
            # saber CUÁL se lleva el dinero es justo lo que se viene a buscar aquí.
            quien = (
                f"{entidades[0]['entidad']} concentra"
                if cuantas == 1
                else f"Las {cuantas} primeras concentran"
            )
            partes.append(f"{quien} el {pct(acumulado / bloque['pim'])} ({soles(acumulado)}).")

    partes.append("El Gobierno Regional no entra en este ámbito: son municipalidades.")
    return " ".join(partes)


def todas(cuerpo: dict, soles=soles_web, pct=pct_web) -> dict[str, str | None]:
    """Las cuatro frases del tablero, tal como viajan en el payload y las imprime el reporte."""
    return {
        "ejecucion": ejecucion(
            cuerpo["agregados"],
            _mes_del_corte(cuerpo) if cuerpo.get("es_parcial") else "",
            soles,
            pct,
        ),
        "procesos": procesos(cuerpo["procesos"], cuerpo["sin_clasificar"], soles, pct),
        "tendencia": tendencia(cuerpo["tendencia"], soles, pct),
        "proyectos": proyectos(cuerpo["proyectos"], soles, pct),
    }


#: Cómo se llama cada polígono del mapa, con su artículo: «provincia» es femenino y «los 13
#: provincias» es exactamente el descuido que delata una frase generada.
_POLIGONO = {
    "distrital": ("distrito", "distritos", "los"),
    "provincial": ("provincia", "provincias", "las"),
}


def distribucion(caja: dict, metrica: str, nivel: str, soles=soles_web, pct=pct_web) -> str | None:
    """Lo que el diagrama de caja enseña y el coroplético no puede.

    El mapa reparte el color en cinco tramos y el último se traga toda la cola: con el PIM
    distrital de 2026 arranca en S/ 216.445, así que un distrito de 220 mil y otro de 9,3
    millones salen del mismo color. Esta frase dice dónde está la mitad de los polígonos, cuántos
    se salen del rango y quién es el mayor — que es exactamente lo que el color aplana.

    Se calla lo que no tiene: sin atípicos no se escribe «0 quedan fuera», que sería ruido.
    """
    if not caja.get("n"):
        return None

    es_dinero = metrica != "pct_ejecucion"
    formato = soles if es_dinero else pct
    singular, plural, articulo = _POLIGONO.get(nivel, _POLIGONO["distrital"])
    partes = [
        f"La mitad de {articulo} {caja['n']} {plural} está entre {formato(caja['q1'])} y "
        f"{formato(caja['q3'])}."
    ]

    atipicos = caja.get("atipicos") or []
    if atipicos:
        mayor = atipicos[0]
        cuantos = (
            "Uno queda fuera de ese rango" if len(atipicos) == 1
            else f"{len(atipicos)} quedan fuera de ese rango"
        )
        partes.append(f"{cuantos}; el mayor, {mayor['nombre']}, con {formato(mayor['valor'])}.")

    # Los ceros solo estorban en el eje logarítmico del dinero: el % de ejecución se dibuja en
    # una escala lineal de 0 a 100 y un 0 % cabe perfectamente. Y se dicen «con S/ 0» y no «sin
    # presupuesto», que sería falso en el devengado: un distrito puede tener PIM y no haber
    # gastado nada.
    if es_dinero and caja.get("ceros"):
        cuantos = caja["ceros"]
        cual = singular if cuantos == 1 else plural
        partes.append(
            f"{cuantos} {cual} con S/ 0 no entra{'' if cuantos == 1 else 'n'} en la escala."
        )
    return " ".join(partes)
