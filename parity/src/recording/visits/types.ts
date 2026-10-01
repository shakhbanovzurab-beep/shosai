// Визит записи: персона открывает адрес, при необходимости действует на странице,
// и всё, что фронтенд получил от /v1, становится фикстурой
// `fixtures/<id>.<язык>.json`. Визит записывается на каждом своём языке.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../../fixtures/format.ts";
import type { Translate } from "../../i18n/texts.ts";

/** Языки записи по умолчанию — языки полной матрицы съёмки. */
export const DEFAULT_LANGUAGES: readonly string[] = ["ru", "en"];

export interface VisitContext {
  readonly language: string;
  /** Тексты интерфейса черновика на языке записи. */
  readonly t: Translate;
}

/**
 * Ответ, который стенд записи дать не может (сервер LiveKit, внешние API), но от
 * которого зависит, какие ещё запросы сделает страница. Запись отвечает им вместо
 * API и сохраняет обмен как синтетический, с причиной.
 */
export interface VisitStub {
  readonly method: string;
  readonly path: string;
  readonly status: number;
  readonly body: JsonValue;
  readonly reason: string;
}

export interface Visit {
  /** Путь фикстуры без языка и расширения: `<раздел>/<экран>`. */
  readonly id: string;
  /** Ключ персоны засева (recording/seed/personas.py); null — аноним. */
  readonly persona: string | null;
  /** Адрес под ORIGIN, вместе с /app. */
  readonly url: string;
  /** Селектор, который есть только на нужном экране: без него запись отклоняется. */
  readonly marker: (t: Translate) => string;
  readonly act?: (page: Page, context: VisitContext) => Promise<void>;
  /**
   * Визит меняет данные. Его персона не встречается в других визитах: кэши API
   * черновика живут по пользователю, и изменение не должно попасть в чужую запись.
   * На каждом языке изменение должно быть своим (адрес почты, имя) — иначе
   * второй язык увидел бы результат первого.
   */
  readonly mutates?: boolean;
  /**
   * Страна посетителя (ISO 3166-1 alpha-2), по умолчанию RU. Черновик выбирает
   * по ней валюту и способы оплаты; в бою её сообщает Cloudflare заголовком.
   */
  readonly country?: string;
  /**
   * Языки записи, по умолчанию DEFAULT_LANGUAGES. Язык задаёт и wh.lang, и язык
   * профиля персоны: черновик переключает интерфейс на язык профиля.
   */
  readonly languages?: readonly string[];
  /** Дополнительные ключи localStorage: имя анонимного зрителя трансляции. */
  readonly storage?: Readonly<Record<string, string>>;
  /** Ключи sessionStorage до загрузки страницы: заявка зрителя на вход в эфир. */
  readonly session?: Readonly<Record<string, string>>;
  /**
   * Запросы «МЕТОД путь», которые запись не пропускает к API: они остаются без
   * ответа и в фикстуру не попадают. Только для запросов, которые черновик
   * повторяет без конца (список зала студии), — их ответ задаёт состояние.
   */
  readonly hold?: readonly string[];
  readonly stubs?: readonly VisitStub[];
}
