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
};

export type Nivel = 1 | 2 | 3 | 4;

export type ClasificacionPeligro = {
  codigo_ccpp: string;
  peligro: string;
  peligro_slug: string;
  /**
   * El `TIP_PELIG` de la fuente (Geodinamica interna/externa, Metereologicas). Aquí había un
   * `tipo` que el API dejó de enviar y que nadie actualizó: la ficha lo pintaba y mostraba «—»
   * en las 3,238 fichas sin que `tsc` pudiera avisar, porque el tipo lo declaraba.
   */
  categoria_geo: string;
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

/**
 * `/api/peligros/frecuencia/provincia/{ubigeo4}/` — lo que pinta el gráfico de /peligros.
 *
 * **Ojo con el vocabulario**, que en pantalla va al revés que en el modelo: la UI llama
 * *evento* a lo que aquí es `eventos` (Huayco, Deslizamiento… 21) y *tipo de evento* a lo que
 * aquí es `familias` (Geodinámica externa, Meteorológicos… 4). Los rótulos los pone el
 * frontend; el API conserva los nombres de sus modelos.
 */
export type FrecuenciaProvincia = {
  provincia: string;
  ubigeo: string;
  total: number;
  /** Sin esto la cifra engaña: 77 con 1 de 8 distritos no se compara con 608 con 8 de 8. */
  distritos_con_registro: number;
  distritos_en_provincia: number;
  /** Rango que **abarca** el conjunto, no un periodo común: cada distrito trae el suyo. */
  periodo: string | null;
  periodos_distintos: number;
  eventos: Array<{
    evento: string;
    slug: string;
    categoria: string;
    /** De aquí sale el color de la barra. */
    categoria_slug: string;
    conteo: number;
  }>;
  familias: Array<{ categoria: string; slug: string; conteo: number }>;
  /**
   * Distritos que declaran subtotales sin desagregar por evento (ADR-D1). Su total entra en
   * `familias` y **no** en `eventos`, así que las dos agrupaciones no suman igual a propósito
   * y la pantalla tiene que decirlo.
   */
  sin_desglose: Array<{ distrito: string; total: number }>;
  total_sin_desglose: number;
  fuente: string | null;
  fuente_url: string | null;
};

/** Un distrito con emergencias en la capa del visor (`/api/peligros/frecuencia/geojson/`). */
export type PuntoEmergencias = {
  ubigeo: string;
  distrito: string;
  provincia: string;
  total: number;
  rango_fecha: string | null;
  /** `null` cuando la fuente declara subtotales sin desagregar. */
  evento_top: string | null;
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
  fecha_implementacion: string | null;
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
 * Cómo se identifica un ejercicio en cualquier payload de Inversión.
 *
 * Espejo exacto de `apps.inversion.consultas.datos_ejercicio`, y lo comparten los siete
 * payloads que nombran un ejercicio. Estaba escrito a mano en cada uno, que es la forma segura
 * de que un día una pantalla no pueda decir de qué año son las cifras que pinta.
 *
 * `es_parcial` dice qué **no** es el dato —su % de ejecución no se compara con el de un año
 * completo—; `en_curso` y `corte_legible` dicen qué **es**.
 */
export type InversionEjercicio = {
  anio: number;
  /** "anual" o "AAAA-MM". Es el dato; para enseñarlo va `corte_legible`. */
  corte: string;
  /** El corte en palabras («junio de 2026»). Cadena vacía si el año está completo. */
  corte_legible: string;
  /** El devengado no cubre el año entero. */
  es_parcial: boolean;
  /**
   * El año fiscal todavía no ha terminado. **No es sinónimo de `es_parcial`**: un corte a junio
   * de un año ya pasado es parcial sin estar en curso, y llamarlo «en curso» sería mentir.
   */
  en_curso: boolean;
};

/**
 * Comparación de una municipalidad contra otro ejercicio.
 *
 * `comparable` es falso cuando los dos ejercicios tienen cortes distintos: un 47.7 % a junio
 * contra un 83 % de un año completo no es una caída de ejecución. El Δ se muestra igual —así se
 * decidió— pero **siempre marcado**, y la marca viaja aquí para que ningún cliente tenga que
 * redescubrir la regla.
 */
export type InversionComparacionFila = InversionEjercicio & {
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

export type InversionPuntoTendencia = InversionEjercicio & {
  fuente: string;
  pia: number;
  pim: number;
  devengado: number;
};

/** Una municipalidad con presupuesto en obra, en el desglose de «Proyectos de inversión». */
export type InversionEntidadProyectos = {
  codigo: string;
  entidad: string;
  ambito: string;
  provincia: string;
  pim: number;
  pim_proyectos: number;
  /** Cuánto del PIM del 0068 de ESA municipalidad es obra. */
  pct_proyectos: number | null;
};

export type Inversion = InversionEjercicio & {
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
    entidades_con_devengado: number;
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
  /**
   * Quién tiene el PIM de proyectos. `agregados.pim_proyectos` solo dice cuánto; sin saber en
   * cuántas manos está, un 40 % se lee como si todas hicieran obra, y casi ninguna la hace.
   * `de` es el total de entidades del ámbito: es lo que da sentido a «24 de 116».
   */
  proyectos: {
    pim: number;
    con_proyectos: number;
    de: number;
    entidades: InversionEntidadProyectos[];
  };
  tendencia: InversionPuntoTendencia[];
  /**
   * Lo que cada gráfico dice, ya redactado (ADR-D6: la frase viaja con el dato).
   * Se escribe en `apps/inversion/declaraciones.py` y la imprimen la SPA y el PDF; redactarla
   * en el cliente dejaría dos versiones que un día no dirían lo mismo.
   */
  declaraciones: {
    ejecucion: string | null;
    procesos: string | null;
    tendencia: string | null;
    proyectos: string | null;
  };
  ejercicios: InversionEjercicio[];
  /** Solo con `comparar_con`: los agregados del otro ejercicio y sus deltas. */
  comparacion?: InversionComparacionAgregada;
};

export type InversionComparacionAgregada = InversionEjercicio & {
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
export type InversionSerieAnio = InversionEjercicio & {
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

export type InversionEntidadDetalle = InversionEjercicio & {
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

/** Una fila del coroplético: un distrito o una provincia (`/api/inversion/mapa/`). */
export type InversionMapaFila = {
  /** Seis dígitos a nivel distrital, cuatro a nivel provincial. Casa con `UBIGEO`/`IDPROV`. */
  ubigeo: string;
  nombre: string;
  provincia: string | null;
  /** Solo a nivel distrital: el polígono enlaza con la ficha de su municipalidad. */
  codigo_entidad: string | null;
  entidad: string | null;
  entidades: number;
  pia: number;
  pim: number;
  devengado: number;
  saldo: number;
  /** null = PIM cero: no hay avance que calcular, y no es un 0 %. */
  pct_ejecucion: number | null;
};

/** Las métricas que se pueden pintar. Las tres de dinero llevan cortes; el % los tiene fijos. */
export type MetricaMapa = "pia" | "pim" | "devengado" | "pct_ejecucion";

export type InversionMapa = InversionEjercicio & {
  nivel: "distrital" | "provincial";
  ambito: string;
  filas: InversionMapaFila[];
  /** Cuatro quintiles por métrica de dinero. Pueden repetirse: la leyenda dibuja el tramo vacío. */
  cortes: Record<"pia" | "pim" | "devengado", number[]>;
  /**
   * Lo que este nivel no puede atribuir a ningún polígono (ADR-D6). No se reparte: se declara.
   * `motivo` viene redactado del backend para que la advertencia viaje con el dato.
   */
  no_ubicado: {
    pia: number;
    pim: number;
    devengado: number;
    entidades: number;
    motivo: string;
  };
  poligonos: { pintados: number; sin_dato: number; motivo: string };
};

export type InversionMapaResponse =
  | { disponible: false; motivo: string }
  | ({ disponible: true } & InversionMapa);

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
  tipo: "noticia" | "articulo" | "opinion" | "publicacion" | "base_datos";
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
  publicacion: "Publicación",
  base_datos: "Base de datos",
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
  menu: { top: EnlaceMenu[]; header: EnlaceMenu[]; footer: EnlaceMenu[] };
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
