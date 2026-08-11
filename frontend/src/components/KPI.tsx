/**
 * Tarjeta de cifra: la unidad de las filas de indicadores del sitio.
 *
 * Estaba duplicada en `Inversion.tsx` y `PeligroDetalle.tsx` con el mismo markup, y la ficha de
 * municipalidad iba a ser la tercera copia. `mono` es la variante que usa la ficha de centro
 * poblado para las coordenadas, donde la cifra es un identificador y no una magnitud.
 */
export default function KPI({
  label,
  value,
  sub,
  mono = false,
}: {
  label: string;
  value: string;
  sub?: string;
  mono?: boolean;
}) {
  return (
    <div className="card p-5">
      <div className="text-xs text-ink-600">{label}</div>
      <div
        className={`mt-1 font-display font-extrabold text-2xl text-mountain-900 ${
          mono ? "font-mono text-base" : ""
        }`}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-ink-600">{sub}</div>}
    </div>
  );
}
