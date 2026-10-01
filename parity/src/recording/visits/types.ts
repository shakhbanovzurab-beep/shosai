// Визит записи: персона открывает адрес, при необходимости действует на странице,
// и всё, что фронтенд получил от /v1, становится фикстурой `fixtures/<id>.json`.

import type { Page } from "@playwright/test";

export interface Visit {
  /** Путь фикстуры без расширения: `<раздел>/<экран>`. */
  readonly id: string;
  /** Ключ персоны засева (recording/seed/personas.py); null — аноним. */
  readonly persona: string | null;
  /** Адрес под ORIGIN, вместе с /app. */
  readonly url: string;
  /** Селектор, который есть только на нужном экране: без него запись отклоняется. */
  readonly marker: string;
  readonly act?: (page: Page) => Promise<void>;
  /**
   * Страна посетителя (ISO 3166-1 alpha-2), по умолчанию RU. Черновик выбирает
   * по ней валюту и способы оплаты; в бою её сообщает Cloudflare заголовком.
   */
  readonly country?: string;
  /**
   * Язык интерфейса (wh.lang), по умолчанию ru. Черновик учитывает его наравне
   * со страной: русский язык закрывает мировой набор кнопок соцвхода.
   */
  readonly language?: string;
  /**
   * Визит меняет данные. Его персона не встречается в других визитах: кэши API
   * черновика живут по пользователю, и изменение не должно попасть в чужую запись.
   */
  readonly mutates?: boolean;
}
