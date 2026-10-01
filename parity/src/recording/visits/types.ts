// Визит записи: персона открывает адрес, при необходимости действует на странице,
// и всё, что фронтенд получил от /v1, становится фикстурой
// `fixtures/<id>.<язык>.json`. Визит записывается на каждом своём языке.

import type { Page } from "@playwright/test";

import type { Translate } from "../../i18n/texts.ts";

/** Языки записи по умолчанию — языки полной матрицы съёмки. */
export const DEFAULT_LANGUAGES: readonly string[] = ["ru", "en"];

export interface VisitContext {
  readonly language: string;
  /** Тексты интерфейса черновика на языке записи. */
  readonly t: Translate;
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
}
