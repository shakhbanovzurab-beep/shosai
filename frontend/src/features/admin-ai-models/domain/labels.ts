import type { AiDataSource } from "./contract";

/** Where the page's numbers come from, as the provider card names it. */
export const SOURCE_LABEL: Record<AiDataSource, string> = {
  backend: "Бэкенд Leo",
  openrouter: "OpenRouter, расходы — демо",
  demo: "Демо-данные",
};
