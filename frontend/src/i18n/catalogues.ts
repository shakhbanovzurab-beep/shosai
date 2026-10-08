import type { LanguageCode } from "@/lib/language";

import type { Messages } from "./messages-type";
import { catalogueUrls } from "virtual:i18n-catalogues";

// Один загруженный каталог на язык; неудачная загрузка не запоминается, следующая попытка повторит запрос.
const loaded = new Map<LanguageCode, Messages>();
const pending = new Map<LanguageCode, Promise<Messages>>();

async function fetchCatalogue(language: LanguageCode): Promise<Messages> {
  const response = await fetch(catalogueUrls[language]);
  if (!response.ok) throw new Error(`Каталог ${language} не загрузился: HTTP ${response.status}`);
  const messages = (await response.json()) as Messages;
  loaded.set(language, messages);
  return messages;
}

/** Все пространства имён одного языка поверх английского (слиты при сборке), скачиваются один раз. */
export function loadCatalogue(language: LanguageCode): Promise<Messages> {
  const ready = loaded.get(language);
  if (ready) return Promise.resolve(ready);
  let request = pending.get(language);
  if (!request) {
    request = fetchCatalogue(language).finally(() => pending.delete(language));
    pending.set(language, request);
  }
  return request;
}

/** Каталог языка, уже загруженный loadCatalogue, — для отрисовки без ожидания. */
export function loadedCatalogue(language: LanguageCode): Messages {
  const messages = loaded.get(language);
  if (!messages) throw new Error(`Каталог ${language} ещё не загружен`);
  return messages;
}
