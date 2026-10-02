import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AppRoot } from "@/composition/AppRoot";
import { startTheme } from "@/core/theme/themeStore";
import "@/core/styles/main.css";

const container = document.getElementById("root");
if (container === null) throw new Error("В index.html нет элемента #root");

// Оформление поднимается до первого рендера: компоненты читают уже применённую тему.
startTheme();

createRoot(container).render(
  <StrictMode>
    <AppRoot />
  </StrictMode>,
);
