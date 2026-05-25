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
  tipo: string | null;
  nivel: Nivel;
  fuente: string | null;
  fuente_url: string | null;
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

export const TIPOS_PELIGRO = [
  "Sismo",
  "Heladas",
  "Bajas temperaturas",
  "Friaje",
  "Sequía",
  "Lluvias",
  "Inundación",
  "Incendios Forestales",
  "Movimientos en masa",
] as const;

export type TipoPeligro = (typeof TIPOS_PELIGRO)[number];
