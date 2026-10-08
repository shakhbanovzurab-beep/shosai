import type { HtmlTagDescriptor, Plugin, ResolvedConfig } from "vite";

import { preferenceBootScript } from "../src/features/preferences/domain/boot-script";
import { languageBootScript } from "../src/i18n/boot-language";
import { LANGUAGE_CODES } from "../src/lib/language";
import { createHash } from "node:crypto";
import { writeFileSync } from "node:fs";
import { join } from "node:path";

const DEV_CATALOGUES = Object.fromEntries(LANGUAGE_CODES.map((code) => [code, `/__i18n/${code}.json`]));

/** Хеш встроенного скрипта в формате CSP: граница (F4) разрешает ровно эти скрипты. */
export const cspHash = (code: string) => `'sha256-${createHash("sha256").update(code).digest("base64")}'`;

/**
 * Встраивает в <head> два скрипта до первой отрисовки: настройки интерфейса и язык с предзагрузкой его
 * каталога. Других встроенных скриптов у кабинета нет; их хеши сборка пишет в dist/csp-hashes.json.
 */
export function bootScripts(): Plugin {
  let config: ResolvedConfig;
  const hashes = new Set<string>();
  return {
    name: "whisperer:boot-scripts",
    enforce: "post",
    configResolved(resolved) {
      config = resolved;
    },
    transformIndexHtml: {
      order: "post",
      handler(_html, context) {
        let catalogues: Record<string, string> = DEV_CATALOGUES;
        if (context.bundle) {
          catalogues = {};
          for (const output of Object.values(context.bundle)) {
            if (output.type !== "asset") continue;
            const match = output.names.map((name) => /^messages-(.+)\.json$/.exec(name)).find(Boolean);
            if (match) catalogues[match[1]] = `${config.base}${output.fileName}`;
          }
        }
        const scripts = [preferenceBootScript(), languageBootScript(catalogues)];
        for (const code of scripts) hashes.add(cspHash(code));
        return scripts.map<HtmlTagDescriptor>((children) => ({ tag: "script", children, injectTo: "head-prepend" }));
      },
    },
    closeBundle() {
      if (config.command !== "build") return;
      const body = `${JSON.stringify({ "script-src": [...hashes].sort() }, null, 2)}\n`;
      writeFileSync(join(config.build.outDir, "csp-hashes.json"), body);
    },
  };
}
