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
  /**
   * Máximo de los peligros que sobreviven a los filtros de la petición; `null` = sin dato con
   * esos filtros. Lo anota el API (`/api/ccpp/`), no se calcula en el cliente: es la unidad que
   * comparten la tabla, la grilla de resultados y el color de los símbolos del mapa.
   */
  nivel?: Nivel | null;
  /**
   * **Todos** los peligros del centro poblado que pasan los filtros, no solo el máximo, y en
   * el mismo orden con el que el mapa elige el ícono. Es lo que lista la tabla: el nivel
   * máximo es un resumen, y con 3.4 peligros de media por lugar escondía lo que se consulta.
   */
  peligros?: PeligroDeCcpp[];
};

export type PeligroDeCcpp = { slug: string; nombre: string; nivel: Nivel };

/** Ficha completa: `/api/ccpp/{codigo}/`. */
export type CentroPobladoDetalle = CentroPoblado & {
  clasificaciones: ClasificacionPeligro[];
  /**
   * La ficha sí publica la población, aunque el listado y el mapa ya no (ADR-A17): aquí es un
   * atributo del centro poblado, no una escala con la que compararlo contra los otros 8,967.
   */
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

/**
 * La unidad de Inversión es la **municipalidad**, no el distrito: quien tiene PIA, PIM y
 * devengado es la entidad ejecutora, y una provincial gestiona presupuesto de toda su
 * provincia. `ubigeo_distrito` es su sede, y puede ser null cuando no casa con el padrón.
 */
export type InversionEntidad = {
  codigo: string;
  entidad: string;
  ambito: "distrital" | "provincial" | "mancomunidad" | "regional" | "nacional";
  ubigeo_distrito: string | null;
  distrito: string | null;
  provincia: string | null;
  pia: number;
  pim: number;
  devengado: number;
  /** null = no se puede calcular (PIM cero), que no es lo mismo que 0 %. */
  pct_ejecucion: number | null;
  saldo: number;
  variacion_pia_pim: number;
  pct_variacion_pia_pim: number | null;
  /** Presupuesto de la entidad entera. null = no se puede calcular, nunca 0. */
  pia_institucional: number | null;
  pim_institucional: number | null;
  devengado_institucional: number | null;
  pct_0068_institucional: number | null;
  pim_proyectos: number;
  pim_actividades: number;
  pct_proyectos: number | null;
  /** Solo con `comparar_con`. Ver `InversionComparacionFila`. */
  comparacion?: InversionComparacionFila;
};

/**
 * Comparación de una municipalidad contra otro ejercicio.
 *
 * `comparable` es falso cuando los dos ejercicios tienen cortes distintos: un 47.7 % a junio
 * contra un 83 % de año cerrado no es una caída de ejecución. El Δ se muestra igual —así se
 * decidió— pero **siempre marcado**, y la marca viaja aquí para que ningún cliente tenga que
 * redescubrir la regla.
 */
export type InversionComparacionFila = {
  anio: number;
  corte: string;
  es_parcial: boolean;
  comparable: boolean;
  /** La municipalidad no tenía presupuesto del 0068 ese año: los deltas son null, no cero. */
  sin_presupuesto: boolean;
  pia: number | null;
  pim: number | null;
  devengado: number | null;
  pct_ejecucion: number | null;
  delta_pim: number | null;
  pct_delta_pim: number | null;
  delta_devengado: number | null;
  delta_pct_ejecucion: number | null;
};

export type InversionProceso = {
  slug: string;
  nombre: string;
  color: string;
  pim: number;
  devengado: number;
  pct: number | null;
};

export type InversionPuntoTendencia = {
  anio: number;
  corte: string;
  /** Corte a mitad de año: su % de ejecución no se compara con el de un año cerrado. */
  es_parcial: boolean;
  fuente: string;
  pia: number;
  pim: number;
  devengado: number;
};

export type Inversion = {
  anio: number;
  corte: string;
  es_parcial: boolean;
  fuente: string;
  ambito: string;
  unidad: string;
  agregados: {
    pia: number;
    pim: number;
    devengado: number;
    pct_ejecucion: number | null;
    saldo: number;
    variacion_pia_pim: number;
    entidades_con_presupuesto: number;
    entidades_en_ambito: number;
    /** Los tres suman solo las entidades con dato, las mismas que el porcentaje de abajo. */
    pia_institucional: number | null;
    pim_institucional: number | null;
    devengado_institucional: number | null;
    pct_0068_institucional: number | null;
    entidades_con_institucional: number;
    pim_proyectos: number;
    pim_actividades: number;
    pct_proyectos: number | null;
  };
  procesos: InversionProceso[];
  /** Lo que el catálogo aún no imputa a ningún proceso. No se reparte ni se esconde. */
  sin_clasificar: { pim: number; devengado: number; pct: number | null };
  tendencia: InversionPuntoTendencia[];
  ejercicios: InversionEjercicio[];
  /** Solo con `comparar_con`: los agregados del otro ejercicio y sus deltas. */
  comparacion?: InversionComparacionAgregada;
};

export type InversionEjercicio = { anio: number; corte: string; es_parcial: boolean };

export type InversionComparacionAgregada = {
  anio: number;
  corte: string;
  es_parcial: boolean;
  comparable: boolean;
  agregados: Inversion["agregados"];
  deltas: {
    pia: number;
    pim: number;
    devengado: number;
    pct_pim: number | null;
    pct_ejecucion: number | null;
  };
};

/** Un año de la historia de una municipalidad: `/api/inversion/entidades/{codigo}/`. */
export type InversionSerieAnio = {
  anio: number;
  corte: string;
  es_parcial: boolean;
  fuente: string;
  pia: number;
  pim: number;
  devengado: number;
  pct_ejecucion: number | null;
  saldo: number;
  variacion_pia_pim: number;
  pct_variacion_pia_pim: number | null;
  pia_institucional: number | null;
  pim_institucional: number | null;
  devengado_institucional: number | null;
  pct_0068_institucional: number | null;
};

export type InversionActividad = {
  codigo: string;
  nombre: string;
  origen: "actividad" | "proyecto";
  /** null = el catálogo aún no la imputa a ningún proceso. */
  proceso: string | null;
  proceso_slug: string | null;
  pia: number;
  pim: number;
  devengado: number;
  pct_ejecucion: number | null;
};

export type InversionEntidadDetalle = {
  entidad: {
    codigo: string;
    nombre: string;
    ambito: InversionEntidad["ambito"];
    ambito_nombre: string;
    ubigeo_distrito: string | null;
    distrito: string | null;
    provincia: string | null;
    /** No casa con el padrón de distritos: cuenta en los totales, pero no se cruza con él. */
    sin_territorio: boolean;
  };
  anio: number;
  corte: string;
  es_parcial: boolean;
  fuente: string;
  serie: InversionSerieAnio[];
  procesos: InversionProceso[];
  sin_clasificar: { pim: number; devengado: number; pct: number | null };
  actividades: InversionActividad[];
  ejercicios: InversionEjercicio[];
};

export type InversionDetalleResponse =
  | { disponible: false; motivo: string }
  | ({ disponible: true } & InversionEntidadDetalle);

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
  /** No lo usa /peligros —la población salió del visor (ADR-A17)—; sí el comparador de distritos. */
  poblacion_total: number;
  por_ccpp: {
    niveles: Record<"1" | "2" | "3" | "4", number>;
    sin_clasificar: number;
  };
  por_peligro: Array<{
    peligro: string;
    slug: string;
    niveles: Record<"1" | "2" | "3" | "4", number>;
    /**
     * Centros poblados con ESTE peligro tras los filtros. Coincide con la suma de `niveles`
     * y no por casualidad: la base impide dos clasificaciones del mismo peligro en un mismo
     * centro poblado, así que **dentro de una fila las dos unidades son la misma**. Por eso la
     * grilla de resultados puede rotular «centros poblados» sin ambigüedad; la de 3.4× solo
     * aparece al sumar la columna entre tipos.
     */
    centros_poblados: number;
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

// --- Inversión (PP 0068) ---------------------------------------------------
// El estado «sin datos» sigue siendo un modo válido: mientras ningún ejercicio esté publicado,
// el endpoint responde `disponible: false` y la ruta muestra su estado vacío.
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
  altitud: number | null;
  /** 0 = sin dato. Categoría propia, no "nivel bajo". */
  nivel: number;
  /**
   * Slug del peligro que gana (mayor nivel; a igualdad, el primero del catálogo). Es la FORMA
   * del ícono en el mapa. Lo decide el servidor para que el símbolo y el popup no discrepen.
   * `""` = sin dato.
   */
  peligro: string;
  /**
   * Clasificaciones que este punto aporta con los filtros puestos; 0 si no cumple ninguno.
   * Es lo que el visor suma para rotular cada grupo — la unidad de las 10,978, no la de 3,238.
   */
  clasificaciones: number;
  /** Desglose serializado: las propiedades de un feature agrupado deben ser escalares. */
  peligros: string;
} & {
  /**
   * Tres familias de claves numeradas, todas escalares porque una fuente agrupada no admite
   * otra cosa, y **solo se emiten las ocupadas** para no inflar un payload de 2 MB:
   *
   * - `n1`…`n4` — cuántas clasificaciones de ese nivel tiene el punto. Lo suman los grupos.
   * - `p_<slug>` — presencia de ese tipo (0/1). También lo suman los grupos.
   * - `s0`…`s8` y `n_0`…`n_8` — **las ranuras de la corona**: un peligro por ranura, en orden
   *   de nivel descendente. El nivel lleva guion bajo justo para no chocar con `n1`…`n4`.
   */
  [clave: string]: string | number | null;
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
