import { ExternalLink } from "lucide-react";

type Props = {
  fuente: string;
  url?: string | null;
};

export default function SourceLink({ fuente, url }: Props) {
  if (!url) {
    return <span className="text-xs text-ink-600">Fuente: {fuente}</span>;
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs text-ink-600 hover:text-mountain-700"
    >
      Fuente: <span className="underline underline-offset-2">{fuente}</span>
      <ExternalLink className="w-3 h-3" />
    </a>
  );
}
