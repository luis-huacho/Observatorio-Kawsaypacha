import { urlEmbed } from "@/lib/video";

type Props = {
  url: string;
  titulo?: string;
};

/** Reproductor embebido 16:9. No pinta nada si la URL no es de YouTube ni Vimeo. */
export default function Video({ url, titulo = "Video" }: Props) {
  const src = urlEmbed(url);
  if (!src) return null;

  return (
    <div className="aspect-video w-full overflow-hidden rounded-xl border border-mountain-900/10 bg-mountain-900">
      <iframe
        src={src}
        title={titulo}
        className="w-full h-full"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
        loading="lazy"
      />
    </div>
  );
}
