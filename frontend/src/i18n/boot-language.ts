// Относительный путь: модуль читает и сборка (tooling/boot-script.ts), где алиаса @ ещё нет.
import { DEFAULT_LANGUAGE, LANGUAGE_CODES, LANGUAGE_COOKIE, languageDirection } from "../lib/language";
import { ADMIN_LANGUAGE } from "./config";

/**
 * Код до первой отрисовки: язык страницы по правилу resolveLocale, `lang` и `dir` на <html> и предзагрузка
 * каталога этого языка, чтобы он скачивался параллельно с кодом приложения.
 */
export function languageBootScript(catalogueUrls: Readonly<Record<string, string>>): string {
  const directions = Object.fromEntries(LANGUAGE_CODES.map((code) => [code, languageDirection(code)]));
  return `
    (function () {
      var root = document.documentElement;
      var path = window.location.pathname;
      var language = ${JSON.stringify(DEFAULT_LANGUAGE)};
      if (path === "/admin" || path.indexOf("/admin/") === 0) {
        language = ${JSON.stringify(ADMIN_LANGUAGE)};
      } else {
        var match = document.cookie.split("; ").find(function (c) {
          return c.indexOf(${JSON.stringify(`${LANGUAGE_COOKIE}=`)}) === 0;
        });
        var chosen = match ? decodeURIComponent(match.split("=")[1]) : null;
        if (chosen && ${JSON.stringify(LANGUAGE_CODES)}.indexOf(chosen) >= 0) language = chosen;
      }
      root.lang = language;
      root.dir = ${JSON.stringify(directions)}[language];
      var url = ${JSON.stringify(catalogueUrls)}[language];
      if (url) {
        var link = document.createElement("link");
        link.rel = "preload";
        link.as = "fetch";
        link.href = url;
        link.crossOrigin = "anonymous";
        document.head.appendChild(link);
      }
    })();
  `;
}
