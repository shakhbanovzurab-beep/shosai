import { DEFAULT_LANGUAGE, type LanguageCode } from "@/lib/language";

import { withFallback } from "./fallback";
import { type Messages, NAMESPACES } from "./namespaces";
import { readFile } from "node:fs/promises";
import path from "node:path";

// Catalogs are read from disk on the server rather than imported: a dynamic `import()` over every language and
// namespace made the bundler compile each of the ~1,000 files as a module, adding over a gigabyte to `next build`.
const MESSAGES_DIR = path.join(process.cwd(), "src/i18n/messages");
// Production keeps each file once; development rereads it so an edited catalog shows on the next request.
const cache = new Map<string, Promise<unknown>>();

const readNamespace = async (file: string): Promise<unknown> => JSON.parse(await readFile(file, "utf8"));

function loadNamespace(language: LanguageCode, namespace: string): Promise<unknown> {
  const file = path.join(MESSAGES_DIR, language, `${namespace}.json`);
  if (process.env.NODE_ENV !== "production") return readNamespace(file);
  let pending = cache.get(file);
  if (!pending) {
    pending = readNamespace(file);
    // A failed read is not kept, so a file that appears later is still found.
    pending.catch(() => cache.delete(file));
    cache.set(file, pending);
  }
  return pending;
}

// A translation missing a whole namespace falls back to English instead of failing the page;
// `npm run i18n:check` keeps that from shipping. English itself must load.
const loadCatalogs = async (language: LanguageCode): Promise<Messages> =>
  Object.fromEntries(
    await Promise.all(
      NAMESPACES.map(async (namespace) => [
        namespace,
        language === DEFAULT_LANGUAGE
          ? await loadNamespace(language, namespace)
          : await loadNamespace(language, namespace).catch(() => ({})),
      ]),
    ),
  );

/** Every namespace of one language, over English so a gap never shows a raw key. */
export async function loadMessages(language: LanguageCode): Promise<Messages> {
  if (language === DEFAULT_LANGUAGE) return loadCatalogs(language);
  const [english, translation] = await Promise.all([loadCatalogs(DEFAULT_LANGUAGE), loadCatalogs(language)]);
  return withFallback(english, translation);
}
