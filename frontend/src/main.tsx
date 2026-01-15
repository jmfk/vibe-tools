import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import 'highlight.js/styles/github-dark.css';

console.log("Main.tsx loading...");

const rootElement = document.getElementById("root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
