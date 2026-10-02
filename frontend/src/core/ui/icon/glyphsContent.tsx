import type { ReactElement } from "react";

// Глифы содержимого: файлы, направления, вид, задачи и списки.
// Сетка 24 × 24, обводка задаётся в Icon.tsx; залитые глифы помечены на месте.
export const CONTENT_GLYPHS = {
  arrowLeft: <path d="M19 12H5M12 19l-7-7 7-7"/>,
  filter:   <path d="M4 4h16l-6 8v6l-4 2v-8L4 4Z"/>,
  more:     <><circle cx="6" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="18" cy="12" r="1.4"/></>,
  bell:     <><path d="M6 8a6 6 0 0 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9Z"/><path d="M10 21a2 2 0 0 0 4 0"/></>,
  logout:   <><path d="M9 4H4v16h5"/><path d="M14 12h7M18 8l4 4-4 4"/></>,
  mic:      <><rect x="9" y="3" width="6" height="12"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"/></>,
  zap:      <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/>,
  layers:   <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5M3 18l9 5 9-5"/></>,
  flask:    <><path d="M9 3h6M10 3v6l-5 11h14L14 9V3"/></>,
  refresh:  <><path d="M21 12a9 9 0 0 1-15.5 6.3L3 16"/><path d="M3 12a9 9 0 0 1 15.5-6.3L21 8"/><path d="M21 3v5h-5M3 21v-5h5"/></>,
  doc:      <><rect x="5" y="3" width="14" height="18"/><path d="M8 8h8M8 12h8M8 16h5"/></>,
  variable: <><path d="M5 4a14 14 0 0 0 0 16M19 4a14 14 0 0 1 0 16"/><path d="M9 10h2l2 4h2M11 14l2-4"/></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></>,
  shield:   <path d="M12 3 4 6v6c0 4.5 3.2 8.6 8 9 4.8-.4 8-4.5 8-9V6l-8-3Z"/>,
  pin:      <><path d="M12 17v5"/><path d="M9 11V3h6v8l3 3v2H6v-2l3-3Z"/></>,
  clip:     <path d="M21.4 11.05 12.25 20.2a5 5 0 0 1-7.07-7.07l9.19-9.19a3 3 0 0 1 4.24 4.24l-8.49 8.49a1.5 1.5 0 0 1-2.12-2.12l7.78-7.78"/>,
  // Полосы разной длины — это аудиодорожка, а не симметричная «галочка звука».
  // Сетка 4…20, а не 5…21: с учётом square-каптов чернила занимают 3.1…20.9,
  // центр ровно 12 — прежняя сетка давала 13, и глиф был сдвинут вправо на 1.
  voicewave: <><path d="M4 8v8"/><path d="M8 3v18"/><path d="M12 6v12"/><path d="M16 4v16"/><path d="M20 9v6"/></>,
  flag:     <><path d="M5 3v18"/><path d="M5 4h14l-3 4 3 4H5"/></>,
  send:     <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z"/>,
  arrowUp:   <path d="M12 19V5M5 12l7-7 7 7"/>,
  arrowDown: <path d="M12 5v14M5 12l7 7 7-7"/>,
  eye:       <><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></>,
  eyeOff:    <><path d="M3 3l18 18"/><path d="M10.6 10.6a3 3 0 0 0 4.2 4.2"/><path d="M9.9 5.1A10.5 10.5 0 0 1 12 5c6.5 0 10 7 10 7a18 18 0 0 1-3.2 4.1M6.1 6.1A18 18 0 0 0 2 12s3.5 7 10 7a10.5 10.5 0 0 0 3-.4"/></>,
  expand:    <><path d="M15 3h6v6"/><path d="M21 3l-8 8"/><path d="M9 21H3v-6"/><path d="M3 21l8-8"/></>,
  collapse:  <><path d="M21 9h-6V3"/><path d="M15 9l6-6"/><path d="M3 15h6v6"/><path d="M9 15l-6 6"/></>,
  maximize:  <><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M16 3h3a2 2 0 0 1 2 2v3"/><path d="M21 16v3a2 2 0 0 1-2 2h-3"/><path d="M8 21H5a2 2 0 0 1-2-2v-3"/></>,
  minimize:  <><path d="M3 8h3a2 2 0 0 0 2-2V3"/><path d="M16 3v3a2 2 0 0 0 2 2h3"/><path d="M21 16h-3a2 2 0 0 0-2 2v3"/><path d="M8 21v-3a2 2 0 0 0-2-2H3"/></>,
  // Трекер и «Влияние» встречи — СПИСОК ЗАДАЧ: галочка плюс строка, дважды.
  // Прежний `kanban` рисовал три столбика разной высоты и в ряду с `trend`
  // читался диаграммой, а не задачами; имя тоже сменилось на честное.
  tasks:     <><path d="m3 8 2.2 2.2L9 5"/><path d="M12.5 7.5h8.5"/><path d="m3 17 2.2 2.2L9 14"/><path d="M12.5 16.5h8.5"/></>,
  board:     <><rect x="3" y="3" width="18" height="18"/><path d="M9 3v18M15 3v18"/></>,
  grip:      <><circle cx="9" cy="6" r="1.2"/><circle cx="15" cy="6" r="1.2"/><circle cx="9" cy="12" r="1.2"/><circle cx="15" cy="12" r="1.2"/><circle cx="9" cy="18" r="1.2"/><circle cx="15" cy="18" r="1.2"/></>,
  grid:      <><rect x="4" y="4" width="7" height="7"/><rect x="13" y="4" width="7" height="7"/><rect x="4" y="13" width="7" height="7"/><rect x="13" y="13" width="7" height="7"/></>,
  list:      <><path d="M8 6h12M8 12h12M8 18h12"/><circle cx="4" cy="6" r="1.3"/><circle cx="4" cy="12" r="1.3"/><circle cx="4" cy="18" r="1.3"/></>,
} satisfies Record<string, ReactElement>;
