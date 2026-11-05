import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { ProvedorSessao } from "./sessao";

ReactDOM.createRoot(document.getElementById("raiz")!).render(
  <React.StrictMode>
    <ProvedorSessao>
      <App />
    </ProvedorSessao>
  </React.StrictMode>,
);
