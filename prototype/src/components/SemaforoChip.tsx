import type { Nivel } from "@/lib/types";
import { NIVEL_BG, NIVEL_LABEL } from "@/lib/semaforo";

type Props = {
  nivel: Nivel;
  showNumber?: boolean;
  className?: string;
};

export default function SemaforoChip({ nivel, showNumber = true, className = "" }: Props) {
  return (
    <span className={`chip border ${NIVEL_BG[nivel]} ${className}`}>
      {showNumber && <span className="font-mono font-semibold">{nivel}</span>}
      {NIVEL_LABEL[nivel]}
    </span>
  );
}
