import "@amceds/shared/ui.css";
import "./app.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App client={api} />
  </StrictMode>,
);
