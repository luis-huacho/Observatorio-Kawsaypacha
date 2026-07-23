import { Inbox } from "lucide-react";
import type { ReactNode } from "react";

type Props = {
  title?: string;
  message?: string;
  action?: ReactNode;
};

export default function EmptyState({
  title = "Sin resultados",
  message = "No encontramos información con los filtros actuales.",
  action,
}: Props) {
  return (
    <div className="card p-8 text-center text-ink-600">
      <div className="w-14 h-14 rounded-full bg-mountain-100 text-mountain-700 grid place-items-center mx-auto mb-3">
        <Inbox className="w-7 h-7" />
      </div>
      <div className="font-display font-semibold text-lg text-ink-900">{title}</div>
      <p className="mt-1 text-sm">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
