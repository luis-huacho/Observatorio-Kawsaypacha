import { AlertCircle } from "lucide-react";

type Props = {
  className?: string;
  label?: string;
};

export default function MockBadge({ className = "", label = "Dato referencial" }: Props) {
  return (
    <span
      className={`chip border border-mock/40 bg-mock/10 text-mock ${className}`}
      title="Este dato es referencial / mock y será reemplazado por datos oficiales en una fase posterior."
    >
      <AlertCircle className="w-3 h-3" />
      {label}
    </span>
  );
}
