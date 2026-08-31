import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

import AvisoDescarga from "./AvisoDescarga";

/**
 * El botón de una descarga, con su estado real.
 *
 * Los cuatro botones de descarga del sitio eran `<a href>` a pelo, y el servidor tarda: la ayuda
 * memoria de `/peligros` **3,7-4,0 s** (renderiza el mapa con un Chromium headless) y el reporte
 * de `/inversion` 4,4 s. Durante esos segundos la página no cambiaba en absoluto —en escritorio
 * salva el indicador del propio navegador; en móvil, que es donde el TDR pide que el sitio sirva,
 * no se ve nada— y el visitante volvía a pulsar.
 *
 * Y no era solo la espera. **El límite de descargas es 30/hora por IP** (`DescargaThrottle`), y
 * una oficina entera comparte IP detrás de un NAT: al pasarse, el servidor responde 429 y con un
 * `<a href>` eso se veía como una pestaña con JSON crudo, o como nada. Ahora se explica.
 *
 * **Sigue siendo un `<a href>`, no un `<button>`**, y esa es la decisión que hace que no se pierda
 * nada: `onClick` intercepta el clic normal y descarga por `fetch`, pero un clic con
 * Ctrl/Cmd/Shift/Alt o con el botón central **se deja pasar al navegador**, igual que «abrir en
 * pestaña nueva» y «guardar enlace como» del menú contextual. Con un `<button>` las tres
 * desaparecerían.
 *
 * Lo que **no** se hace: ni encolar la generación (cuatro segundos no justifican una tarea, una
 * fila de BD y un archivo guardado en un `MEDIA_ROOT` que nginx sirve entero como estático
 * público), ni fingir el estado con un temporizador, que diría «listo» cuando no lo está.
 */

type Estado = "idle" | "descargando" | "error";

export type BotonDescargaProps = {
  url: string;
  /** El texto del botón en reposo. */
  children: React.ReactNode;
  /** Qué se está generando, para el aviso: «la ayuda memoria de SICUANI». */
  descripcion: string;
  /** La etiqueta mientras trabaja: «Generando PDF…», «Preparando Excel…». */
  etiquetaEnCurso: string;
  icono: React.ReactNode;
  /**
   * El nombre con el que guardar si `Content-Disposition` no llega.
   *
   * No es paranoia: la cabecera solo se lee cross-origin si el servidor la expone
   * (`CORS_EXPOSE_HEADERS`), y un bundle nuevo contra un backend viejo es un estado real durante
   * un despliegue. Sin esto el archivo se guardaría con el identificador del blob, sin extensión.
   */
  nombreDeReserva: string;
  className?: string;
  title?: string;
  /** Se dispara en el clic. Es `sendBeacon`, no espera respuesta. */
  onDescargar?: () => void;
  /** Cuando no se puede pedir todavía (en `/peligros`, sin distrito elegido). */
  deshabilitado?: boolean;
  /** Por qué está deshabilitado. Se pinta como `title`. */
  motivo?: string;
  claseDeshabilitado?: string;
};

/** `attachment; filename="ayuda-memoria-sicuani-20260830.pdf"` ⇒ el nombre. */
function nombreDeLaCabecera(cabecera: string | null): string {
  if (!cabecera) return "";
  // `filename*=UTF-8''…` tiene prioridad sobre `filename=` cuando el nombre lleva acentos; los
  // que compone el backend van sin ellos, pero leerlo cuesta una línea y evita un nombre
  // percent-codificado el día que alguno los lleve.
  const extendido = /filename\*=UTF-8''([^;]+)/i.exec(cabecera);
  if (extendido) {
    try {
      return decodeURIComponent(extendido[1]);
    } catch {
      /* cabecera mal formada: se cae al `filename=` de abajo */
    }
  }
  return /filename="?([^";]+)"?/i.exec(cabecera)?.[1]?.trim() ?? "";
}

export default function BotonDescarga({
  url,
  children,
  descripcion,
  etiquetaEnCurso,
  icono,
  nombreDeReserva,
  className = "",
  title,
  onDescargar,
  deshabilitado = false,
  motivo,
  claseDeshabilitado = "",
}: BotonDescargaProps) {
  const [estado, setEstado] = useState<Estado>("idle");
  const [error, setError] = useState("");
  const abortarRef = useRef<AbortController | null>(null);

  // Si el visitante se va de la página, un PDF de cuatro segundos ya no le sirve a nadie: se
  // aborta en vez de dejar al servidor terminando un trabajo que nadie va a recoger.
  useEffect(() => () => abortarRef.current?.abort(), []);

  if (deshabilitado) {
    return (
      <span title={motivo} className={claseDeshabilitado || className}>
        {icono}
        {children}
      </span>
    );
  }

  const descargar = async (evento: React.MouseEvent<HTMLAnchorElement>) => {
    // Ctrl/Cmd/Shift/Alt y el botón central son «ábrelo aparte»: se dejan al navegador.
    if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey || evento.button !== 0)
      return;
    evento.preventDefault();
    if (estado === "descargando") return;

    onDescargar?.();
    setError("");
    setEstado("descargando");

    const control = new AbortController();
    abortarRef.current = control;
    try {
      const respuesta = await fetch(url, { signal: control.signal });
      if (!respuesta.ok) {
        setError(
          respuesta.status === 429
            ? "Has pedido demasiadas descargas en la última hora. Espera un momento y vuelve a intentarlo."
            : "No se pudo generar el archivo. Inténtalo de nuevo en unos minutos."
        );
        setEstado("error");
        return;
      }

      const nombre =
        nombreDeLaCabecera(respuesta.headers.get("Content-Disposition")) || nombreDeReserva;
      const blob = await respuesta.blob();
      const enlace = document.createElement("a");
      enlace.href = URL.createObjectURL(blob);
      enlace.download = nombre;
      document.body.appendChild(enlace);
      enlace.click();
      enlace.remove();
      // NO se revoca en este mismo tick: hacerlo puede abortar la descarga antes de que el
      // navegador llegue a leer el blob.
      setTimeout(() => URL.revokeObjectURL(enlace.href), 60_000);
      setEstado("idle");
    } catch (e) {
      // El abortado es el visitante yéndose de la página: no es un fallo que contarle a nadie.
      if ((e as Error)?.name === "AbortError") return;
      setError("No se pudo descargar el archivo. Comprueba tu conexión e inténtalo de nuevo.");
      setEstado("error");
    } finally {
      abortarRef.current = null;
    }
  };

  const trabajando = estado === "descargando";
  return (
    <>
      <a
        href={url}
        onClick={descargar}
        title={title}
        aria-busy={trabajando}
        aria-disabled={trabajando}
        className={`${className}${trabajando ? " opacity-60 pointer-events-none" : ""}`}
      >
        {trabajando ? <Loader2 className="w-4 h-4 motion-safe:animate-spin" /> : icono}
        {trabajando ? etiquetaEnCurso : children}
      </a>
      {(trabajando || estado === "error") && (
        <AvisoDescarga
          descripcion={descripcion}
          error={estado === "error" ? error : undefined}
          onCerrar={() => setEstado("idle")}
        />
      )}
    </>
  );
}
