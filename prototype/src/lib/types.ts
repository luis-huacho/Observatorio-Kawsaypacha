export type CentroPoblado = {
  codigo: string;
  nombre: string;
  categoria: string;
  departamento: string;
  provincia: string;
  distrito: string;
  ubigeo_distrito: string;
  lat: number | null;
  lon: number | null;
  altitud: number | null;
  poblacion: number | null;
};

export type Nivel = 1 | 2 | 3 | 4;

export type ClasificacionPeligro = {
  codigo_ccpp: string;
  peligro: string;
  peligro_slug: string;
  tipo: string | null;
  nivel: Nivel;
  fuente: string | null;
  fuente_url: string | null;
};

export type EventoEmergencia = {
  evento: string;
  slug: string;
  conteo: number;
};

export type CategoriaEmergencia = {
  categoria: string;
  slug: string;
  total: number;
  /** La fuente declaró un subtotal pero no lo desagregó por tipo de evento. */
  solo_total: boolean;
  eventos: EventoEmergencia[];
};

export type FrecuenciaDistrito = {
  ubigeo: string;
  distrito: string;
  provincia: string;
  /** Cada distrito trae su propio periodo de observación; no hay uno regional. */
  rango_fecha: string | null;
  fuente: string | null;
  fuente_url: string | null;
  desglose_disponible: boolean;
  total: number;
  categorias: CategoriaEmergencia[];
};

export type Medida = {
  _mock?: boolean;
  id: string;
  slug: string;
  titulo: string;
  peligro: string;
  ambito: "comunal" | "distrital" | "provincial" | "regional";
  resultado: "exito" | "leccion" | "mal_adaptacion";
  ubigeo: string;
  comunidad: string;
  resumen_corto: string;
  contenido?: string;
  video_url: string | null;
  imagen: string | null;
  tags: string[];
};

export type InversionDistrito = {
  ubigeo: string;
  distrito: string;
  provincia: string;
  pia: number;
  pim: number;
  devengado: number;
  pct_prevencion: number;
  pct_respuesta: number;
};

export type Inversion = {
  _mock?: boolean;
  anio: number;
  agregados: {
    pim_total: number;
    ejecutado: number;
    porcentaje_ejecucion: number;
    municipios_con_ppr_0068: number;
  };
  por_distrito: InversionDistrito[];
  comparacion_prevencion_respuesta: {
    prevencion_total: number;
    respuesta_total: number;
  };
  tendencia: Array<{ anio: number; pim: number; devengado: number }>;
};

export type PrioridadDistrito = {
  ubigeo: string;
  distrito: string;
  provincia: string;
  score: number;
  nivel: "alto" | "medio" | "bajo";
  variables: {
    exposicion: number;
    poblacion_expuesta: number;
    pobreza: number;
    infraestructura: number;
    agua: number;
    frecuencia: number;
  };
};

export type Prioridades = {
  _mock?: boolean;
  metodologia: string;
  pesos_default: PrioridadDistrito["variables"];
  scores: PrioridadDistrito[];
};

export type Norma = {
  _mock?: boolean;
  id: string;
  titulo: string;
  tipo: "Ley" | "DS" | "RM" | "RJ" | "Ordenanza";
  ambito: "nacional" | "regional" | "local";
  fecha: string;
  resumen: string;
  url_oficial: string | null;
  analisis_predes: string | null;
};

/**
 * Los nueve peligros del Excel canónico, con el nombre EXACTO que trae la columna PELIGRO.
 * Ojo: no coincide con el nombre de la hoja en dos casos ("Lluvias" → "Lluvias intensas",
 * "Incendios Forestales" → "Incendios forestales"). El slug es la clave que usan los tiles
 * vectoriales del visor (propiedad `nivel_<slug>`).
 */
export const PELIGROS = [
  { nombre: "Sismo", slug: "sismo" },
  { nombre: "Heladas", slug: "heladas" },
  { nombre: "Bajas temperaturas", slug: "bajas_temperaturas" },
  { nombre: "Friaje", slug: "friaje" },
  { nombre: "Sequía", slug: "sequia" },
  { nombre: "Lluvias intensas", slug: "lluvias_intensas" },
  { nombre: "Inundación", slug: "inundacion" },
  { nombre: "Incendios forestales", slug: "incendios_forestales" },
  { nombre: "Movimientos en masa", slug: "movimientos_en_masa" },
] as const;

export const TIPOS_PELIGRO = PELIGROS.map((p) => p.nombre) as readonly string[];

export type TipoPeligro = (typeof PELIGROS)[number]["nombre"];
export type SlugPeligro = (typeof PELIGROS)[number]["slug"];
