// Состояние экрана для съёмки: какая фикстура, в каких ячейках, что изменить в
// ответах, что сделать на странице и по какому маркеру понять, что это оно.
// Идентификаторы — из инвентаря (parity/inventory/).

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import type { Translate } from "../i18n/texts.ts";
import type { Scope, ViewportName } from "../matrix.ts";

/** Ответ вместо записанного: синтетический, с обязательной причиной. */
export interface OverrideResponse {
  readonly status: number;
  readonly body: JsonValue;
  readonly contentType?: string;
}

/**
 * Один ответ переопределения: hold — без ответа (загрузка), fail — сетевой сбой,
 * recorded — записанный ответ (последовательность «первые два как в записи, третий
 * висит»).
 */
export type OverrideReply = OverrideResponse | OverrideMerge | OverrideOpenStream | "hold" | "fail" | "recorded";

/** Поток, который не заканчивается: тело уходит сразу, соединение остаётся открытым. */
export interface OverrideOpenStream {
  readonly open: string;
  readonly contentType?: string;
}

/**
 * Записанный ответ с правкой: поля `merge` вливаются в его JSON-тело (объекты —
 * глубоко, массивы и значения — заменой). Вариант экрана на тех же данных:
 * «стенограмма обрезана», «место почти кончилось».
 */
export interface OverrideMerge {
  readonly merge: { readonly [key: string]: JsonValue };
}

export interface Override {
  readonly method: string;
  /** Путь API без строки запроса; заменяет все записанные ответы этого пути. */
  readonly path: string;
  /**
   * Ответ на каждый запрос пути или последовательность: n-й запрос получает
   * n-й ответ, последний повторяется (первая проба падает, вторая висит).
   */
  readonly respond: OverrideReply | readonly OverrideReply[];
  /** Почему ответ не записан: чего стенд записи не может воспроизвести. */
  readonly reason: string;
}

/** Веб-сокет состояния: кадры подставного сервера после подключения и в ответ странице. */
export interface SocketScript {
  /** Путь сокета: `/v1/ws/voice`. */
  readonly path: string;
  /** Кадры сразу после подключения. */
  readonly frames: readonly JsonValue[];
  /**
   * Кадры после первого сообщения страницы. Голос Leo отвечает фазами на звук
   * микрофона: пришедшая раньше фаза перетёрлась бы «Слушаю…» при его старте.
   */
  readonly afterClient?: readonly JsonValue[];
  /** Почему кадры заданы: чего стенд записи не может воспроизвести. */
  readonly reason: string;
}

/** То, что нужно для ключей localStorage состояния: id пользователя фикстуры. */
export interface StorageSeed {
  readonly userId: string;
}

export interface StateContext {
  readonly language: string;
  readonly t: Translate;
}

export interface State {
  /** Идентификатор из инвентаря: `auth.login.default`. */
  readonly id: string;
  /** Визит, чья фикстура даёт данные: `auth/login`. */
  readonly fixture: string;
  /** Адрес, если он отличается от адреса визита (та же фикстура, другой экран). */
  readonly url?: string;
  /** full — все ячейки матрицы; single — одна (ru, компьютер, светлая). */
  readonly scope: Scope;
  /** Языки, на которых записана фикстура; по умолчанию ru и en для full, ru для single. */
  readonly languages?: readonly string[];
  /** Только эти вьюпорты: выдвижное меню есть лишь на телефоне. По умолчанию — все ячейки охвата. */
  readonly viewports?: readonly ViewportName[];
  /** Состояние снимается и в прогоне по остальным 14 языкам. */
  readonly sweep?: boolean;
  readonly overrides?: readonly Override[];
  readonly act?: (page: Page, context: StateContext) => Promise<void>;
  readonly marker: (t: Translate) => string;
  /** Маркер — тост ошибки: такой тост ожидаем, остальные — признак сбоя. */
  readonly expectsAlert?: boolean;
  /**
   * Состояние — наведение: указатель остаётся там, где его оставило действие.
   * По умолчанию перед снимком он уходит в угол.
   */
  readonly keepPointer?: boolean;
  /** Кадры веб-сокетов: голосовой режим, напоминания. По умолчанию сокеты молчат. */
  readonly sockets?: readonly SocketScript[];
  /**
   * Дополнительные ключи localStorage: то, что фронтенд хранит в браузере
   * (переписка Leo). Ключи зависят от id пользователя фикстуры.
   */
  readonly storage?: (seed: StorageSeed) => Readonly<Record<string, string>>;
  /**
   * Маркер ниже края экрана (конец длинной страницы, низ окна): когда страница
   * успокоилась, поставить его в центр области прокрутки и дождаться покоя ещё раз.
   */
  readonly reveal?: boolean;
  /**
   * Области, закрытые на снимке: значения, которые идут по настоящим часам
   * (обратный отсчёт «через 60 с»), а не по замороженным. Только с причиной.
   */
  readonly mask?: { readonly selectors: (t: Translate) => readonly string[]; readonly reason: string };
  /** Допуск сверх общего при сравнении с v2 — только с причиной. */
  readonly tolerance?: { readonly maxDiffPixelRatio: number; readonly reason: string };
}

export function stateLanguages(state: State): readonly string[] {
  return state.languages ?? (state.scope === "full" ? ["ru", "en"] : ["ru"]);
}
