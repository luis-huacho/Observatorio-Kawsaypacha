import { Download, FileText } from "lucide-react";
import { formatPeso } from "@/lib/semaforo";
import type { ArchivoAdjunto } from "@/lib/types";

/**
 * «Documentos» al pie de una ficha: los anexos descargables.
 *
 * **Es un `<a href download>` y no `BotonDescarga`**, que es el componente de las otras cuatro
 * descargas del sitio. Aquel existe por dos condiciones que aquí no se dan: el servidor tarda
 * unos cuatro segundos en generar el archivo, y hay un límite de 30 descargas por hora que
 * devuelve un 429 que hay que explicar. Un anexo ya está escrito y lo sirve nginx como estático,
 * así que interceptar el clic con `fetch` solo añadiría una espera y un blob por nada.
 *
 * `download` se declara igualmente, aunque el navegador **lo ignora cuando el enlace es
 * cross-origin** —y lo es, porque el API vive en otro dominio (ADR-A14)—: no estorba, y el
 * archivo se guarda con el nombre que trae la URL, que por eso conserva el original.
 *
 * Sin archivos no pinta nada, por el mismo motivo que `ListaEnlaces`.
 */
export default function ListaArchivos({
  archivos,
  titulo = "Documentos",
}: {
  archivos: ArchivoAdjunto[];
  titulo?: string;
}) {
  if (!archivos.length) return null;

  return (
    <section className="mt-8">
      <h2 className="flex items-center gap-2 font-display font-semibold text-mountain-900 mb-3">
        <FileText className="w-4 h-4 text-mountain-700" />
        {titulo}
      </h2>
      <ul className="space-y-2">
        {archivos.map((a, i) => (
          <li key={`${a.archivo}-${i}`}>
            <a
              href={a.archivo}
              download
              className="card flex items-center gap-3 px-4 py-3 hover:border-mountain-900/25"
            >
              <FileText className="w-5 h-5 shrink-0 text-mountain-700" />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-mountain-900">{a.titulo}</span>
                <span className="block text-xs text-ink-600">
                  {a.extension.toUpperCase()} · {formatPeso(a.peso_bytes)}
                </span>
              </span>
              <Download className="w-4 h-4 shrink-0 text-mountain-700" />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
