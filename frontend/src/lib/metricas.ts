/**
 * Métricas internas de uso (requisito 7 del TDR, ADR-A11).
 *
 * Sin cookies, sin identificadores y sin analítica de terceros: se manda el tipo de evento, la
 * ruta y un detalle, y el servidor guarda un hash diario de IP+UA que no permite reidentificar a
 * nadie ni seguirle la pista entre días.
 *
 * Se usa `navigator.sendBeacon`: la petición sobrevive a la navegación que la provoca, que es
 * justo lo que hace falta al registrar una descarga o un cambio de página. Con `fetch` normal, el
 * navegador cancela la petición en cuanto la página se va.
 *
 * El cuerpo va **form-encoded, no JSON**. `application/json` no está en la lista blanca de CORS,
 * así que cada evento dispararía una petición `OPTIONS` de preflight contra otro dominio
 * (ADR-A14) — y el preflight de un beacon no siempre llega a completarse, de modo que la métrica
 * se perdía. `application/x-www-form-urlencoded` es un tipo seguro: no hay preflight, y el
 * FormParser de DRF lo entiende sin código extra. De paso, cada pageview cuesta una petición en
 * vez de dos.
 */
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { urlApi } from "./api";

export type TipoEvento =
  | "pageview"
  | "descarga_pdf"
  | "export_excel"
  | "busqueda"
  | "descarga_documento"
  | "click_capa";

export function registrar(tipo: TipoEvento, ruta: string, detalle = ""): void {
  // Un fallo de métricas nunca debe interrumpir lo que el usuario estaba haciendo, así que todo
  // va envuelto y silenciado: la cifra vale menos que la acción.
  try {
    const cuerpo = new URLSearchParams({ tipo, ruta, detalle });
    const url = urlApi("/metricas/evento/");
    if (navigator.sendBeacon) {
      navigator.sendBeacon(
        url,
        new Blob([cuerpo.toString()], { type: "application/x-www-form-urlencoded" })
      );
      return;
    }
    void fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: cuerpo.toString(),
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* sin métricas, pero sin molestar */
  }
}

/** Registra una visita por cada cambio de ruta. Se monta una sola vez, en `Layout`. */
export function useMetricaPagina(): void {
  const { pathname } = useLocation();
  useEffect(() => {
    registrar("pageview", pathname);
  }, [pathname]);
}

/**
 * Descarga de una ayuda memoria. El `detalle` lleva el **ubigeo**: es la métrica que le dice a
 * PREDES qué distritos se están llevando a mesas técnicas (spec 06).
 */
export function registrarAyudaMemoria(ubigeo: string): void {
  registrar("descarga_pdf", "/peligros", ubigeo);
}

export function registrarExport(ruta: string, detalle = ""): void {
  registrar("export_excel", ruta, detalle);
}

export function registrarBusqueda(termino: string): void {
  registrar("busqueda", "/buscar", termino);
}

export function registrarDescargaDocumento(titulo: string): void {
  registrar("descarga_documento", "/recursos", titulo);
}
