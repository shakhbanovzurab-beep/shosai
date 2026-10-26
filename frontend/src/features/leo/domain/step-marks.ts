/** Значок шага на ленте «думает»: поиск в сети, поиск в данных человека или точка — по коду действия. */
export type StepMark = "web" | "search" | "dot";

// Коды действий бывают плоскими (`web_search`, `search_knowledge`) и по инструментам (`notes.search`, `web.search`).
const WEB = /^web([._]|$)/;
const SEARCH = /(^|[._])search([._]|$)/;

export function stepMark(action: string): StepMark {
  if (WEB.test(action)) return "web";
  return SEARCH.test(action) ? "search" : "dot";
}
