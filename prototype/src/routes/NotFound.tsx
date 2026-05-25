import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="container-page py-20 text-center">
      <div className="font-display text-7xl font-extrabold text-mountain-100">404</div>
      <h1 className="font-display text-2xl font-bold text-mountain-900 mt-2">Página no encontrada</h1>
      <p className="text-ink-600 mt-2">La ruta solicitada no existe.</p>
      <Link to="/" className="btn-primary mt-6 inline-flex">Volver al inicio</Link>
    </div>
  );
}
