import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer className="mt-16 bg-mountain-900 text-mountain-100">
      <div className="container-page py-10 grid gap-8 md:grid-cols-4">
        <div className="md:col-span-2">
          <div className="font-display text-lg font-bold text-white">Observatorio Kawsaypacha</div>
          <p className="text-sm mt-2 text-mountain-100/80 max-w-md">
            Monitoreo y seguimiento de la gestión del riesgo de desastres y la adaptación
            al cambio climático en la región Cusco, Perú. Operado por PREDES.
          </p>
          <p className="mt-3 text-xs text-mountain-100/60">
            Datos provenientes de SIGRID-CENEPRED, INEI, MEF (PPR 0068), SENAMHI, INGEMMET, IGP, ANA, INAIGEM.
          </p>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-mountain-100/60 mb-3">Ventanas</div>
          <ul className="space-y-2 text-sm">
            <li><Link className="text-mountain-100 hover:text-white no-underline" to="/peligros">Peligros</Link></li>
            <li><Link className="text-mountain-100 hover:text-white no-underline" to="/medidas">Medidas</Link></li>
            <li><Link className="text-mountain-100 hover:text-white no-underline" to="/inversion">Inversión</Link></li>
            <li><Link className="text-mountain-100 hover:text-white no-underline" to="/prioridades">Prioridades</Link></li>
          </ul>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-mountain-100/60 mb-3">Más</div>
          <ul className="space-y-2 text-sm">
            <li><Link className="text-mountain-100 hover:text-white no-underline" to="/normativa">Normativa</Link></li>
            <li><Link className="text-mountain-100 hover:text-white no-underline" to="/recursos">Recursos</Link></li>
            <li><Link className="text-mountain-100 hover:text-white no-underline" to="/sobre">Sobre el observatorio</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-mountain-700/50">
        <div className="container-page py-4 text-xs text-mountain-100/60 flex flex-wrap gap-3 items-center justify-between">
          <span>© {new Date().getFullYear()} PREDES — Centro de Estudios y Prevención de Desastres</span>
          <span className="px-2 py-0.5 rounded-full bg-mock/20 text-mock font-semibold">
            Prototipo de validación
          </span>
        </div>
      </div>
    </footer>
  );
}
