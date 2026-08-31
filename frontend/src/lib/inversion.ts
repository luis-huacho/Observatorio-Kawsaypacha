import type {
  Inversion,
  InversionEjercicio,
  InversionProceso,
  InversionPuntoTendencia,
} from "./types";

/**
 * Cómo se NOMBRA un ejercicio en pantalla.
 *
 * La ventana solo decía qué **no** era el dato («no comparable con el de un ejercicio
 * cerrado») y obligaba a deducir por descarte que el año que se está mirando es el corriente.
 * Aquí se decide una vez cómo se llama, para que el selector, la banda de aviso, la tendencia y
 * la ficha de la municipalidad no lo redacten cada una a su manera.
 *
 * La palabra «cerrado» no aparece a propósito: es jerga contable —año fiscal terminado y
 * liquidado— y define el dato por su contrario. Donde hace falta el término de comparación se
 * dice «un año completo» o «un año ya terminado».
 */

/** «junio de 2026» ⇒ «junio». Vacío si el ejercicio no tiene corte que nombrar. */
export function mesDelCorte({ corte_legible }: InversionEjercicio): string {
  return corte_legible.split(" de ")[0] || "";
}

/**
 * El estado del ejercicio en dos palabras, o `""` si el año está completo.
 *
 * `en_curso` y `es_parcial` no son lo mismo: un corte a junio de un año ya pasado es parcial sin
 * estar en curso, y el backend los distingue justo para que aquí no se llame «en curso» a algo
 * que ya terminó.
 */
export function estadoEjercicio(e: InversionEjercicio): string {
  if (e.en_curso) return "año fiscal en curso";
  if (e.es_parcial) return "datos parciales";
  return "";
}

/** La opción del desplegable: «2026 · en curso (a junio)». Un `AAAA-MM` crudo no lo lee nadie. */
export function etiquetaEjercicio(e: InversionEjercicio): string {
  if (!e.es_parcial) return String(e.anio);
  const estado = e.en_curso ? "en curso" : "parcial";
  const hasta = mesDelCorte(e);
  return `${e.anio} · ${estado}${hasta ? ` (a ${hasta})` : ""}`;
}

/** El pie de las tablas de tendencia, en el tablero y en la ficha de la municipalidad. */
export const PIE_EJERCICIO_PARCIAL =
  "* Ejercicio en curso o con corte parcial: el devengado no cubre el año completo, así que su " +
  "% de ejecución no se compara con el de un año ya terminado.";

/* --------------------------------------------------------------------------
 * Lo que cada gráfico DICE, en una frase.
 *
 * Un gráfico se deja leer pero no concluye: la conclusión la tiene que sacar quien mira. La
 * ventana la usan autoridades, periodistas y universidades, y lo que necesitan es la frase que
 * se puede copiar. Se redacta aquí y no en el componente para que sea probable sin montar React
 * y para que las cuatro compartan registro.
 *
 * El registro es el de las `.declaracion` del PDF: sujeto = la cifra, presente de indicativo,
 * tercera persona, sin adjetivos valorativos. **Y sin color de semáforo**: `Delta` pinta las
 * subidas en verde porque compara dos ejercicios que el usuario eligió, pero aquí más
 * presupuesto no es automáticamente una buena noticia y teñirlo de verde sería opinar.
 *
 * La palabra «cerrado» no aparece —es jerga contable y hay una prueba e2e que lo fija—: un
 * ejercicio terminado es «completo».
 * ------------------------------------------------------------------------ */

/**
 * «subió»/«bajó» + importe + porcentaje, o `null` si no hay base con la que comparar.
 *
 * El porcentaje sale del mismo `formatPct` que el resto de la ventana, inyectado: escribirlo a
 * mano dejaba «225.8 %» al lado de «47.7%» en la misma frase.
 */
function variacion(
  desde: number,
  hasta: number,
  soles: (n: number) => string,
  pct: (n: number) => string,
): string | null {
  if (!desde) return null;
  const delta = hasta - desde;
  if (delta === 0) return "se mantuvo igual";
  return `${delta > 0 ? "subió" : "bajó"} ${soles(Math.abs(delta))} (${pct(Math.abs(delta / desde))})`;
}

/** Del PIA al PIM y del PIM al devengado: lo que el primer gráfico enseña sin decirlo. */
export function declaracionEjecucion(
  a: Inversion["agregados"],
  corte: string,
  soles: (n: number) => string,
  pct: (n: number) => string,
): string | null {
  if (!a.pim) return null;
  const partes: string[] = [];
  if (a.pia) {
    const signo = a.variacion_pia_pim >= 0 ? "creció" : "se redujo en";
    partes.push(
      `El presupuesto ${signo} ${soles(Math.abs(a.variacion_pia_pim))} ` +
        `(${pct(Math.abs(a.variacion_pia_pim / a.pia))}) entre lo aprobado al abrir el año ` +
        `y lo vigente hoy.`,
    );
  }
  if (a.pct_ejecucion !== null) {
    const cuando = corte ? `Al corte de ${corte} se` : "Se";
    partes.push(`${cuando} ha devengado el ${pct(a.pct_ejecucion)} y quedan ${soles(a.saldo)} por ejecutar.`);
  }
  return partes.length ? partes.join(" ") : null;
}

/** Dónde se concentra el dinero entre los procesos de la GRD, y qué proceso se queda en cero. */
export function declaracionProcesos(
  procesos: InversionProceso[],
  sinClasificar: Inversion["sin_clasificar"],
  soles: (n: number) => string,
  pct: (n: number) => string,
): string | null {
  const conPim = procesos.filter((p) => p.pim > 0);
  if (!conPim.length) return null;
  const mayor = conPim.reduce((a, b) => (b.pim > a.pim ? b : a));

  const partes = [
    `${mayor.nombre} concentra ${mayor.pct === null ? "la mayor parte" : `el ${pct(mayor.pct)}`}` +
      ` del presupuesto vigente (${soles(mayor.pim)}).`,
  ];

  // Un proceso en cero es un hallazgo, no un hueco del gráfico: la barra vacía no se explica sola.
  const enCero = procesos.filter((p) => p.pim === 0).map((p) => p.nombre);
  if (enCero.length === 1) partes.push(`${enCero[0]} no tiene presupuesto en este ejercicio.`);
  else if (enCero.length > 1) {
    // `at(-1)` no está en el target de TS de este proyecto; el índice explícito sí.
    const ultimo = enCero[enCero.length - 1];
    partes.push(
      `${enCero.slice(0, -1).join(", ")} y ${ultimo} no tienen presupuesto en este ejercicio.`,
    );
  }

  // La tenía el PDF y no la pantalla. Es la medida de lo que le falta al catálogo, y se declara
  // en vez de repartirse entre los demás procesos.
  if (sinClasificar.pim > 0) {
    partes.push(
      `${soles(sinClasificar.pim)} cuelgan de códigos que el catálogo aún no imputa a ningún proceso.`,
    );
  }
  return partes.join(" ");
}

/**
 * La tendencia, comparando **los dos últimos ejercicios completos**.
 *
 * Comparar el año en curso con el anterior daría un «el devengado bajó 59 %» que no mide una
 * caída: mide medio año contra un año entero. El corte parcial se nombra aparte, sin número de
 * variación, que es la única forma de que la frase no tenga que desmentirse a renglón seguido.
 */
export function declaracionTendencia(
  tendencia: InversionPuntoTendencia[],
  soles: (n: number) => string,
  pct: (n: number) => string,
): string | null {
  const completos = tendencia.filter((t) => !t.es_parcial);
  const parciales = tendencia.filter((t) => t.es_parcial);
  const partes: string[] = [];

  if (completos.length >= 2) {
    const [previo, ultimo] = completos.slice(-2);
    const pim = variacion(previo.pim, ultimo.pim, soles, pct);
    const devengado = variacion(previo.devengado, ultimo.devengado, soles, pct);
    if (pim && devengado) {
      partes.push(
        `Entre ${previo.anio} y ${ultimo.anio}, los dos últimos ejercicios completos, ` +
          `el presupuesto vigente ${pim} y el gasto ejecutado ${devengado}.`,
      );
    }
  }

  for (const parcial of parciales) {
    partes.push(
      `El ejercicio ${parcial.anio} va al corte de ${mesDelCorte(parcial)} y no se compara con ellos.`,
    );
  }
  return partes.length ? partes.join(" ") : null;
}

/**
 * Cuántas municipalidades tienen obra, y en cuántas manos está el dinero.
 *
 * Es la frase que corrige la lectura que originó este bloque: el porcentaje en proyectos parece
 * alto y se atribuye al Gobierno Regional, que **no está en este ámbito**. Lo que lo explica es
 * que casi ninguna municipalidad tiene proyectos y unas pocas obras se llevan casi todo.
 */
export function declaracionProyectos(
  proyectos: Inversion["proyectos"],
  soles: (n: number) => string,
  pct: (n: number) => string,
): string | null {
  const { con_proyectos: con, de, entidades } = proyectos;
  if (!de) return null;
  if (!con) {
    return "Ninguna municipalidad del ámbito tiene presupuesto en proyectos de inversión: todo el programa está en actividades.";
  }

  const partes = [
    `${con} de las ${de} municipalidades del ámbito tienen presupuesto en proyectos de inversión.`,
  ];

  // Cuántas hacen falta para llegar al 80 %: es la medida de concentración que se entiende sin
  // saber estadística, y la que convierte «parece mucho dinero» en «son estas obras».
  if (con > 1 && proyectos.pim > 0) {
    let acumulado = 0;
    let cuantas = 0;
    for (const e of entidades) {
      acumulado += e.pim_proyectos;
      cuantas += 1;
      if (acumulado / proyectos.pim >= 0.8) break;
    }
    if (cuantas < con) {
      // Con una sola se la nombra en vez de contarla: «Las 1 primeras» no es castellano, y
      // saber CUÁL municipalidad se lleva el dinero es justo lo que se viene a buscar aquí.
      const quien =
        cuantas === 1 ? `${entidades[0].entidad} concentra` : `Las ${cuantas} primeras concentran`;
      partes.push(`${quien} el ${pct(acumulado / proyectos.pim)} (${soles(acumulado)}).`);
    }
  }

  // El ámbito es municipal: el Gobierno Regional tiene sus propios proyectos y no está aquí.
  // Se dice porque es exactamente la lectura equivocada que este desglose viene a corregir.
  partes.push("El Gobierno Regional no entra en este ámbito: son municipalidades.");
  return partes.join(" ");
}
