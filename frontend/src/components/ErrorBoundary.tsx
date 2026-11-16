import { Component, type ErrorInfo, type ReactNode } from "react";

/** Si algo falla al dibujar la pantalla, se muestra un aviso con salida en lugar de dejarla en blanco. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { fallo: boolean }> {
  state = { fallo: false };
  static getDerivedStateFromError() { return { fallo: true }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error("Error de interfaz", error, info.componentStack); }
  render() {
    if (!this.state.fallo) return this.props.children;
    return (
      <div role="alert" className="tema-neu grid min-h-full place-items-center p-6 text-center">
        <div className="neu max-w-sm space-y-3 p-6">
          <h1 className="text-lg font-semibold">Algo no salió como esperábamos</h1>
          <p className="text-sm text-tenue">La pantalla tuvo un error. Tus datos no se perdieron.</p>
          <button onClick={() => window.location.reload()} className="degradado rounded-xl px-4 py-2 text-sm font-semibold text-white">Recargar</button>
        </div>
      </div>
    );
  }
}
