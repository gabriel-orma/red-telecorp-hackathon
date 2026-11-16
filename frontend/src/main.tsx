import { StrictMode } from "react";
import { MotionConfig } from "framer-motion";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource-variable/plus-jakarta-sans";
import "./index.css";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      {/* reducedMotion="user": respeta la preferencia del sistema de reducir el movimiento */}
      <MotionConfig reducedMotion="user"><App /></MotionConfig>
    </ErrorBoundary>
  </StrictMode>,
);
