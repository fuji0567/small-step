import { mount } from "svelte";

import App from "./App.svelte";
import "./styles.css";

mount(App, { target: document.getElementById("app")! });

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/rec/sw.js", { scope: "/rec/" });
  });
}
