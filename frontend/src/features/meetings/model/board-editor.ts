/* Excalidraw берёт шрифты с сайта кабинета (`tooling/board-fonts.ts`), а не с CDN: путь задаётся до его загрузки. */

const ASSETS = `${import.meta.env.BASE_URL}wb/`;

/** Загрузить модуль, которому нужен Excalidraw, — со шрифтами кабинета. */
export function withBoardAssets<T>(load: () => Promise<T>): Promise<T> {
  Object.assign(window, { EXCALIDRAW_ASSET_PATH: ASSETS });
  return load();
}
