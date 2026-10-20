import {
  createFormatter,
  createTranslator,
  type NamespaceKeys,
  type NestedKeyOf,
  type useTranslations,
} from "use-intl";

import { loadCatalogue } from "@/i18n/catalogues";
import { formats } from "@/i18n/formats";
import type { Messages } from "@/i18n/messages-type";
import { cabinetTimeZone } from "@/i18n/time-zone";
import { interfaceLanguage } from "@/lib/api/interface-language";
import { isLanguageCode, type LanguageCode } from "@/lib/language";

/*
 * То, что примерным обработчикам нужно от сервера, — в браузере: ответы JSON, язык запроса, его сообщения
 * и форматтер. Обработчики работают только в разработке и тестах (F2-D1); слайс удаляет свои, когда появляется
 * его API.
 */

/** Ответы JSON в том виде, как их пишут обработчики. */
export const JsonResponse = {
  json: <T>(body: T, init?: ResponseInit) => Response.json(body, init),
};

/** Ошибка в прежней форме FastAPI, `{ "detail": message }`. */
export const detail = (message: string, status: number) => Response.json({ detail: message }, { status });

/** Язык, который просит запрос (`Accept-Language` от слоя данных), или язык страницы. */
export function requestLanguage(request: Request): LanguageCode {
  const asked = request.headers.get("accept-language");
  return asked && isLanguageCode(asked) ? asked : interfaceLanguage();
}

/** Язык страницы. */
export const getLocale = async (): Promise<LanguageCode> => interfaceLanguage();

type Namespace = NamespaceKeys<Messages, NestedKeyOf<Messages>>;

/** Переводчик одного пространства имён — на языке страницы или запрошенном. */
export async function getTranslations<N extends Namespace>(arg: N | { locale: LanguageCode; namespace: N }) {
  const { locale, namespace } = typeof arg === "string" ? { locale: interfaceLanguage(), namespace: arg } : arg;
  const messages = await loadCatalogue(locale);
  const translator = createTranslator({ locale, messages, namespace, formats, timeZone: cabinetTimeZone() });
  // Тот же переводчик, что у экранов (useTranslations): ключи и аргументы ICU проверяются одинаково.
  return translator as unknown as ReturnType<typeof useTranslations<N>>;
}

/** Даты и числа на языке страницы, в часовом поясе и именованных форматах приложения. */
export const getFormatter = async () =>
  createFormatter({ locale: interfaceLanguage(), formats, timeZone: cabinetTimeZone() });
