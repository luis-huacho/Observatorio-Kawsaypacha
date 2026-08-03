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
  /**
   * Máximo de los peligros que sobreviven a los filtros de la petición; `null` = sin dato con
   * esos filtros. Lo anota el API (`/api/ccpp/`), no se calcula en el cliente: es la unidad que
   * comparten la tabla, el panel de distribución y el mapa.
   */
  nivel?: Nivel | null;
};

/** Ficha completa: `/api/ccpp/{codigo}/`. */
export type CentroPobladoDetalle = CentroPoblado & {
  clasificaciones: ClasificacionPeligro[];
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

/** Una foto de la galería de una medida. Espejo del modelo hijo `MedidaImagen` del spec 01. */
export type MedidaImagen = {
  imagen: string;
  pie: string;
  orden: number;
};

export type EnlaceExterno = {
  titulo: string;
  url: string;
};

/** Distrito tal como lo anida el API en el contenido editorial. */
export type DistritoBreve = {
  ubigeo: string;
  nombre: string;
  provincia: string;
};

/** Espejo de `MedidaListaSerializer`: lo que devuelve `/api/medidas/`. */
export type Medida = {
  slug: string;
  titulo: string;
  peligro: string;
  peligro_slug: SlugPeligro | string;
  ambito: "comunal" | "distrital" | "provincial" | "regional";
  resultado: "exito" | "leccion" | "mal_adaptacion";
  distrito: DistritoBreve | null;
  comunidad: string;
  resumen_corto: string;
  /**
   * Portada YA RESUELTA por el servidor: si la pieza no tiene imagen propia, el API devuelve la
   * ilustración institucional de su peligro. La regla vive en el serializer para que ningún
   * cliente la reimplemente (spec 01/02).
   */
  imagen_portada: string;
  imagen_titulo: string;
  palabras_clave: string[];
  destacada: boolean;
  publicado_en: string | null;
};

/** Espejo de `MedidaDetalleSerializer`: `/api/medidas/{slug}/`. */
export type MedidaDetalle = Medida & {
  /** HTML de CKEditor 5, ya saneado en servidor. Se pinta con `ContenidoRico`. */
  contenido: string;
  video_url: string | null;
  galeria: MedidaImagen[];
  enlaces: EnlaceExterno[];
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

/** Espejo del modelo `contenidos.Noticia` del spec 01, para que el port a la API no renombre nada. */
export type Noticia = {
  slug: string;
  titulo: string;
  bajada: string;
  fecha: string;
  tipo: "noticia" | "articulo" | "opinion";
  autor: string;
  /** Ya resuelta por el servidor (propia o ilustración institucional del tipo). */
  imagen_portada: string;
  imagen_titulo: string;
  palabras_clave: string[];
  destacada: boolean;
};

export const TIPOS_NOTICIA: Record<Noticia["tipo"], string> = {
  noticia: "Noticia",
  articulo: "Artículo",
  opinion: "Opinión",
};

/** Espejo de `NormaSerializer`: `/api/normativa/`. */
export type Norma = {
  slug: string;
  titulo: string;
  tipo: "Ley" | "DS" | "RM" | "RJ" | "Ordenanza";
  ambito: "nacional" | "regional" | "local";
  fecha: string;
  anio: number;
  resumen: string;
  analisis_predes: string | null;
  /** Enlace al portal del organismo emisor. */
  url_oficial: string | null;
  /**
   * PDF alojado por PREDES, si existe. Tiene prioridad sobre `url_oficial`: los portales del
   * Estado reorganizan sus URL y un enlace roto inutiliza el repositorio. Los tres estados
   * —PDF, portal, sin enlace— los resuelve `EnlaceNorma`.
   */
  documento_url: string | null;
  imagen_portada: string;
  imagen_titulo: string;
  palabras_clave: string[];
  numero: string;
  estado_vigencia: string;
};

/** Espejo de `NormaDetalleSerializer`: `/api/normativa/{slug}/`. */
export type NormaDetalle = Norma & {
  /** Análisis desarrollado, HTML de CKEditor ya saneado. */
  contenido: string;
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

/** `/api/noticias/{slug}/` — el cuerpo solo viaja en el detalle. */
export type NoticiaDetalle = Noticia & {
  /** HTML de CKEditor ya saneado en servidor. */
  cuerpo: string;
};

// --- Territorio -------------------------------------------------------------
export type Provincia = { ubigeo: string; nombre: string };

export type Distrito = {
  ubigeo: string;
  nombre: string;
  provincia: string;
  ubigeo_provincia: string;
};

// --- Resumen de peligros ----------------------------------------------------
/**
 * `/api/peligros/resumen/`.
 *
 * Trae **las dos unidades rotuladas** porque difieren en 3.4× y confundirlas fue un error real
 * del prototipo: `por_ccpp` cuenta centros poblados una vez en su nivel máximo (la unidad de la
 * tabla y del mapa) y `por_peligro` cuenta clasificaciones. `unidades` las describe en texto
 * para que cualquier gráfico pueda rotularse.
 */
export type ResumenPeligros = {
  total_ccpp: number;
  poblacion_total: number;
  por_ccpp: {
    niveles: Record<"1" | "2" | "3" | "4", number>;
    sin_clasificar: number;
  };
  por_peligro: Array<{
    peligro: string;
    slug: string;
    niveles: Record<"1" | "2" | "3" | "4", number>;
    sin_dato: number;
  }>;
  unidades: { por_ccpp: string; por_peligro: string };
};

// --- Sitio ------------------------------------------------------------------
export type EnlaceMenu = { texto: string; url: string; grupo: string; orden: number };

export type HeroSlide = {
  titulo: string;
  subtitulo: string;
  imagen: string | null;
  cta_texto: string;
  cta_url: string;
  orden: number;
};

export type BloqueTexto = { titulo: string; cuerpo: string };

/** `/api/sitio/`: todo lo administrable del cascarón, en una sola petición. */
export type SitioPayload = {
  config: {
    nombre_sitio: string;
    descripcion_footer: string;
    email_contacto: string;
    telefono: string;
    direccion: string;
    redes: Record<string, string>;
    mensaje_banner: string;
    logo: string | null;
  };
  /** Indexado por clave (`home.hero.titulo`, `sobre.mision`…). */
  bloques: Record<string, BloqueTexto>;
  menu: { header: EnlaceMenu[]; footer: EnlaceMenu[] };
  hero: HeroSlide[];
};

// --- Mapas ------------------------------------------------------------------
export type CapaMapa = {
  slug: string;
  nombre: string;
  descripcion: string;
  /** URL absoluta del .pmtiles; la sirve el dominio del backend. */
  url: string;
  tipo_geometria: "punto" | "linea" | "poligono" | "";
  /** Paint de MapLibre, editable desde el admin sin tocar código. */
  estilo: Record<string, unknown>;
  min_zoom: number;
  max_zoom: number | null;
  visible_por_defecto: boolean;
  orden: number;
  atribucion: string;
  fuente: string;
};

// --- Biblioteca, videos y eventos ------------------------------------------
export type Documento = {
  id: number;
  titulo: string;
  categoria: string;
  categoria_slug: string;
  archivo: string | null;
  url_externa: string | null;
  resumen: string;
  resumen_generado_por_ia: boolean;
  autor_institucion: string;
  fecha_publicacion: string | null;
  paginas: number | null;
  peso_bytes: number | null;
};

export type CategoriaDocumento = { slug: string; nombre: string; orden: number };

export type Video = {
  id: number;
  titulo: string;
  descripcion: string;
  url: string;
  fecha: string;
  tema: string | null;
  tema_slug: string | null;
  duracion: string;
};

export type Evento = {
  id: number;
  titulo: string;
  descripcion: string;
  inicio: string;
  fin: string | null;
  lugar: string;
  modalidad: "presencial" | "virtual" | "mixta";
  url_inscripcion: string | null;
  organizador: string;
};

// --- Comparador -------------------------------------------------------------
export type ComparadorDistrito = {
  ubigeo: string;
  distrito: string;
  provincia: string;
  poblacion: number;
  total_ccpp: number;
  por_ccpp: ResumenPeligros["por_ccpp"];
  por_peligro: ResumenPeligros["por_peligro"];
  frecuencia: FrecuenciaDistrito | null;
  medidas_publicadas: number;
};

export type ComparadorRespuesta = {
  distritos: ComparadorDistrito[];
  /** Los periodos de observación son por distrito: los totales no son comparables sin decirlo. */
  advertencia_periodos: string;
  inversion_disponible: boolean;
};

// --- Inversión (diferida, ADR-D3) ------------------------------------------
export type InversionResponse =
  | { disponible: false; motivo: string }
  | ({ disponible: true } & Inversion);

/** GeoJSON de los puntos del visor (`/api/ccpp/geojson/`). */
export type PuntoCcpp = {
  codigo: string;
  nombre: string;
  categoria: string;
  distrito: string;
  provincia: string;
  ubigeo_distrito: string;
  poblacion: number;
  altitud: number | null;
  /** 0 = sin dato. Categoría propia, no "nivel bajo". */
  nivel: number;
  /** Desglose serializado: las propiedades de un feature agrupado deben ser escalares. */
  peligros: string;
};

/** Catálogo de peligros tal como lo devuelve `/api/peligros/tipos/`. */
export type TipoPeligroApi = {
  slug: string;
  nombre: string;
  categoria_geo: string;
  orden: number;
  descripcion: string;
  icono: string;
  color: string;
};
