import type { InversionDistribucion, MetricaMapa } from "@/lib/types";
import { formatPct, formatSoles } from "@/lib/semaforo";

/**
 * Diagrama de caja de lo que el mapa está pintando.
 *
 * **Existe porque el coroplético no puede enseñar el reparto.** Los quintiles son la escala
 * correcta para un mapa, pero su último tramo se traga toda la cola: con el PIM distrital de
 * 2026 arranca en S/ 216.445, así que un distrito de 220 mil y otro de 9,3 millones salen del
 * mismo color. La mediana es S/ 73.510 y el máximo, PICHARI, **127 veces más**. El mapa se ve
 * plano y la razón no está en el mapa.
 *
 * SVG a mano y no Recharts: el proyecto no usa `ErrorBar`, `Scatter` ni `ComposedChart` en
 * ninguna parte, y componer un diagrama de caja con barras apiladas es más frágil que dibujarlo.
 * El precedente de gráfico hecho a mano ya existe (`ProyectosVsActividades`), y el PDF construye
 * sus SVG con `rect`/`line`/`text`, así que el día que esto pase al papel se traduce casi línea
 * a línea.
 *
 * **Los números NO se calculan aquí.** Vienen del payload del mapa, junto a `cortes` y a los dos
 * `motivo`, por lo mismo (ADR-D6): dos cálculos de la misma mediana acaban discrepando.
 */

/**
 * El alto tiene que dejar sitio a las etiquetas de los cuartiles, que se dibujan POR DEBAJO de
 * la caja: con 78 su línea base caía en `y = 78` —justo el borde del `viewBox`— y se veían
 * cortadas. Un texto que se sale del `viewBox` **no da ningún error**, solo se ve mal, así que
 * hay una prueba e2e que comprueba que cabe.
 */
const ALTO = 96;
const MARGEN = { izq: 8, der: 8, arriba: 26, abajo: 34 };
const ANCHO = 640;
const EJE_Y = MARGEN.arriba + 16;
const ALTO_CAJA = 22;

const COLOR_CAJA = "#0095A4";
const COLOR_EJE = "#9CA3AF";
const COLOR_ATIPICO = "#B8753C";

/**
 * La escala del eje.
 *
 * **El dinero va en logarítmica y no es una preferencia.** Medido sobre 2026: en un eje lineal
 * de 600 px la caja del PIM distrital ocupa **9 píxeles**. Eso no es un diagrama de caja, es un
 * punto, y el gráfico dejaría de decir lo que existe para decir.
 *
 * Dos repliegues, los dos por la misma razón —`log(0)` no existe—:
 *
 * - El **% de ejecución** va siempre lineal, de 0 a 100. Ahí no hay cola que comprimir y un 0 %
 *   es un punto perfectamente válido.
 * - Si `q1` valiera 0 —más de la mitad de los polígonos sin presupuesto— la escala logarítmica
 *   no se puede dibujar y **se repliega a lineal**. Sin esto la caja saldría con `-Infinity` de
 *   borde izquierdo y el SVG no pintaría nada, sin dar ningún error.
 */
function escala(caja: InversionDistribucion, metrica: MetricaMapa) {
  const ancho = ANCHO - MARGEN.izq - MARGEN.der;
  const tope = Math.max(caja.bigote_max, ...caja.atipicos.map((a) => a.valor));

  if (metrica === "pct_ejecucion") {
    return { x: (v: number) => MARGEN.izq + Math.min(1, Math.max(0, v)) * ancho, log: false };
  }
  if (caja.q1 > 0 && tope > 0) {
    // El suelo es el menor positivo que hay que dibujar, no cero: en logarítmica no existe.
    const suelo = Math.max(caja.bigote_min, caja.q1 / 4, 1);
    const [a, b] = [Math.log10(suelo), Math.log10(Math.max(tope, suelo * 10))];
    return {
      x: (v: number) => MARGEN.izq + ((Math.log10(Math.max(v, suelo)) - a) / (b - a)) * ancho,
      log: true,
    };
  }
  const maximo = Math.max(tope, 1);
  return { x: (v: number) => MARGEN.izq + (Math.max(v, 0) / maximo) * ancho, log: false };
}

export type CajaDistribucionProps = {
  caja: InversionDistribucion;
  metrica: MetricaMapa;
  /** «distrito» / «provincia», para el rótulo. */
  unidad: string;
  etiquetaMetrica: string;
};

export default function CajaDistribucion({
  caja,
  metrica,
  unidad,
  etiquetaMetrica,
}: CajaDistribucionProps) {
  // Sin polígonos no hay reparto que enseñar, y una caja vacía se lee como una avería.
  if (!caja.n) return null;

  const f = (v: number) => (metrica === "pct_ejecucion" ? formatPct(v) : formatSoles(v));
  const { x, log } = escala(caja, metrica);
  const medio = EJE_Y + ALTO_CAJA / 2;

  return (
    <figure className="m-0">
      <figcaption className="text-xs text-ink-600 mb-1">
        Cómo se reparte: <strong className="text-mountain-900">{etiquetaMetrica}</strong> por{" "}
        {unidad}, {caja.n} valores
        {log && <span className="text-[11px]"> · escala logarítmica</span>}
      </figcaption>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${ANCHO} ${ALTO}`}
          className="w-full min-w-[22rem]"
          role="img"
          aria-label={caja.frase ?? `Distribución de ${etiquetaMetrica} por ${unidad}`}
        >
          {/* Bigotes: llegan al último valor que NO es atípico, no al máximo. */}
          <line
            x1={x(caja.bigote_min)} x2={x(caja.bigote_max)} y1={medio} y2={medio}
            stroke={COLOR_EJE} strokeWidth="1"
          />
          {[caja.bigote_min, caja.bigote_max].map((v, i) => (
            <line
              key={i} x1={x(v)} x2={x(v)} y1={medio - 6} y2={medio + 6}
              stroke={COLOR_EJE} strokeWidth="1"
            />
          ))}

          {/* La caja: del primer al tercer cuartil. `Math.max(1, …)` para que un rango
              intercuartílico diminuto siga siendo visible en vez de desaparecer. */}
          <rect
            x={x(caja.q1)} y={EJE_Y}
            width={Math.max(1, x(caja.q3) - x(caja.q1))} height={ALTO_CAJA}
            fill={COLOR_CAJA} fillOpacity="0.22" stroke={COLOR_CAJA} strokeWidth="1"
          />
          <line
            x1={x(caja.mediana)} x2={x(caja.mediana)} y1={EJE_Y} y2={EJE_Y + ALTO_CAJA}
            stroke={COLOR_CAJA} strokeWidth="2.5"
          />

          {/* Atípicos (Tukey, 1,5·IQR). El `<title>` da tooltip nativo sin una línea de JS: sin
              el nombre, un punto suelto a la derecha no dice nada. */}
          {caja.atipicos.map((a) => (
            <circle
              key={a.nombre} cx={x(a.valor)} cy={medio} r="3.5"
              fill="none" stroke={COLOR_ATIPICO} strokeWidth="1.4"
            >
              <title>{`${a.nombre}: ${f(a.valor)}`}</title>
            </circle>
          ))}

          {/* Los tres números, escritos. La forma enseña el sesgo, pero leer un cuartil no puede
              depender de medir píxeles — y en logarítmica el ojo no sabe dónde está. */}
          <text x={x(caja.mediana)} y={EJE_Y - 8} textAnchor="middle"
                fontSize="11" fill="#0F172A" fontWeight="600">
            {f(caja.mediana)}
          </text>
          <text x={x(caja.q1)} y={EJE_Y + ALTO_CAJA + 18} textAnchor="middle"
                fontSize="10" fill="#6B7280">
            {f(caja.q1)}
          </text>
          <text x={x(caja.q3)} y={EJE_Y + ALTO_CAJA + 18} textAnchor="middle"
                fontSize="10" fill="#6B7280">
            {f(caja.q3)}
          </text>
        </svg>
      </div>
      <p className="text-[11px] text-ink-600 mt-1">
        La caja va del primer al tercer cuartil y la línea gruesa es la mediana; los círculos son
        los {unidad}s que se salen del rango (pasa el cursor para ver cuáles).
      </p>
    </figure>
  );
}
