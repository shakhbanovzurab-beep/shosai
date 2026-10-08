import { PREFERENCE_REGISTRY } from "./registry";

/**
 * Код, который index.html выполняет до первой отрисовки: читает настройки из cookie или localStorage
 * по реестру и ставит атрибуты `data-*` и тему на <html>, чтобы не было вспышки темы или раскладки.
 * Встраивается плагином сборки (tooling/boot-script.ts); единственный встроенный скрипт страницы.
 */
export function preferenceBootScript(): string {
  return `
    (function () {
      try {
        var root = document.documentElement;
        var REGISTRY = ${JSON.stringify(PREFERENCE_REGISTRY)};

        function readCookie(name) {
          var match = document.cookie.split("; ").find(function(c) {
            return c.startsWith(name + "=");
          });
          return match ? decodeURIComponent(match.split("=")[1]) : null;
        }

        function readLocal(name) {
          try {
            return window.localStorage.getItem(name);
          } catch (e) {
            return null;
          }
        }

        function readPreference(key, definition) {
          var mode = definition.persistence;
          var value = null;

          if (mode === "localStorage") {
            value = readLocal(key);
          }

          if (!value && mode === "client-cookie") {
            value = readCookie(key);
          }

          return definition.values.indexOf(value) >= 0 ? value : definition.defaultValue;
        }

        var preferences = {};

        Object.keys(REGISTRY).forEach(function(key) {
          var definition = REGISTRY[key];
          var value = readPreference(key, definition);

          preferences[key] = value;
          root.setAttribute(definition.attribute, value);
        });

        var mode = preferences.theme_mode;
        var resolvedMode =
          mode === "system" && window.matchMedia
            ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
            : mode === "dark"
              ? "dark"
              : "light";

        root.classList.toggle("dark", resolvedMode === "dark");
        root.style.colorScheme = resolvedMode;

      } catch (e) {
        console.warn("preference boot script:", e);
      }
    })();
  `;
}
