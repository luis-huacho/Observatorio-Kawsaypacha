/**
 * URL de video a URL embebible.
 *
 * El modelo solo guarda la URL que pega el editor (spec 01: `url` YouTube/Vimeo), así que la
 * conversión a `/embed/` es responsabilidad del cliente. La usan el `video_url` suelto de una
 * medida y el `<oembed>` que CKEditor deja dentro del contenido.
 */
export function urlEmbed(url: string): string | null {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\./, "");

    if (host === "youtu.be") {
      const id = u.pathname.slice(1);
      return id ? `https://www.youtube.com/embed/${id}` : null;
    }
    if (host.endsWith("youtube.com")) {
      // Formato watch?v=… y también /embed/… ya listo.
      const id = u.searchParams.get("v") ?? u.pathname.match(/\/embed\/([^/?]+)/)?.[1];
      return id ? `https://www.youtube.com/embed/${id}` : null;
    }
    if (host.endsWith("vimeo.com")) {
      const id = u.pathname.split("/").filter(Boolean).pop();
      return id && /^\d+$/.test(id) ? `https://player.vimeo.com/video/${id}` : null;
    }
    return null;
  } catch {
    // URL malformada: mejor no pintar nada que un iframe roto.
    return null;
  }
}
