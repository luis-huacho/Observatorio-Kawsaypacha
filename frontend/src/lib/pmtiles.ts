import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";

/**
 * Registro del protocolo `pmtiles://` en MapLibre.
 *
 * Vive en un módulo compartido y no en cada componente de mapa **porque la bandera tiene que ser
 * una sola**. Mientras el único mapa con tiles era el visor de peligros, su `let` de módulo
 * bastaba; con dos, cada componente tendría su propia bandera, registraría su propio `Protocol`
 * y el segundo pisaría al primero dejando dos cachés de tiles vivas — un desperdicio silencioso,
 * porque MapLibre no se queja de que le reemplacen un protocolo.
 */
let registrado = false;

export function registrarProtocoloPmtiles(): void {
  if (registrado) return;
  maplibregl.addProtocol("pmtiles", new Protocol().tile);
  registrado = true;
}
