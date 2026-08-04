import { defineConfig, devices } from "@playwright/test";

/**
 * E2E del Observatorio Kallpachakuy (ver `_specs/08-plan-pruebas.md`).
 *
 * En una máquina nueva, primero `./e2e/instalar-dependencias.sh`: instala las librerías de sistema
 * de Chromium, las dependencias de npm y el navegador. Sin las primeras, la suite falla ENTERA con
 * «browserType.launch: Target page, context or browser has been closed», que parece el sitio
 * caído y es una librería ausente. En RHEL/Rocky/Fedora es obligatorio, porque
 * `playwright install --with-deps` solo sabe instalar dependencias en Debian y Ubuntu.
 *
 * Corren contra un stack **ya levantado y sembrado**, no contra un servidor que arranque
 * Playwright: lo que estas pruebas cubren es justo lo que las de API no ven —que el mapa pinte,
 * que los filtros lleguen a la pantalla, que el bundle hable con el backend correcto—, y eso
 * exige el sistema real con sus datos reales.
 *
 *   Desarrollo:        docker compose -f compose.yaml -f compose.dev.yml up -d
 *                      cd frontend && npm run dev      → E2E_URL por defecto
 *   Producción local:  docker compose -f compose.yaml -f compose.local.yml up -d
 *                      E2E_URL=http://localhost npx playwright test
 *
 * La segunda forma es la que vale antes de entregar: prueba el bundle compilado servido por
 * nginx, que es lo que verá PREDES.
 *
 * Con el dev server recién arrancado, **conviene visitar las rutas una vez antes de correr**: Vite
 * compila cada módulo la primera vez que se lo piden, y con varios navegadores en paralelo esa
 * compilación se lleva por delante el timeout de las peticiones al API. No es un fallo del sitio;
 * en modo producción no ocurre porque el bundle ya está construido.
 *
 *   for r in / /peligros /medidas /buscar /inversion; do curl -so /dev/null localhost:5173$r; done
 */
const baseURL = process.env.E2E_URL || "http://localhost:5173";

export default defineConfig({
  testDir: "./e2e",
  // El visor tarda: MapLibre descarga los tiles por rangos y el padrón son ~3 MB de GeoJSON.
  timeout: 60_000,
  expect: { timeout: 15_000 },
  // Sin reintentos en local: un fallo intermitente que se esconde tras un retry es peor que un
  // fallo. En CI uno, para no bloquear por un timeout de red.
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL,
    locale: "es-PE",
    timezoneId: "America/Lima",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "escritorio", use: { ...devices["Desktop Chrome"] } },
    // El TDR pide que el sitio sirva en campo, y en campo se entra desde el móvil.
    { name: "movil", use: { ...devices["Pixel 5"] } },
  ],
});
