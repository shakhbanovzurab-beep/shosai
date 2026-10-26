import type { Plugin } from "vite";

/*
 * Раскладка ELK у Mermaid — 440 КБ gzip, втрое больше бюджета чанка (tooling/check-dist.ts). Кабинет рисует
 * диаграммы раскладкой dagre (diagram-render.ts), а чанк ELK Mermaid грузит, только когда диаграмма сама просит
 * `layout: elk`. Сборка ставит на его место модуль, чья раскладка отказывает, — такая диаграмма показывает свой
 * текст с пометкой. Сам модуль загружается без ошибки: ошибка загрузки чанка перезагрузила бы страницу
 * (src/app/stale-chunk-reload.ts).
 */

const MERMAID = /[\\/]mermaid[\\/]dist[\\/]/;
const ELK_CHUNK = /^\.\/elk-[A-Z0-9]+\.mjs$/;
const STUB = "\0shosai:mermaid-elk-stub";

/** Без ELK в production-сборке; в `npm run dev` Mermaid собран оптимизатором Vite и ELK в нём остаётся. */
export function mermaidWithoutElk(): Plugin {
  return {
    name: "shosai:mermaid-without-elk",
    apply: "build",
    enforce: "pre",
    resolveId(source, importer) {
      return importer !== undefined && MERMAID.test(importer) && ELK_CHUNK.test(source) ? STUB : null;
    },
    load(id) {
      return id === STUB
        ? `export const render = async () => {
            throw new Error("Mermaid ELK layout is not part of the cabinet build");
          };`
        : null;
    },
  };
}
