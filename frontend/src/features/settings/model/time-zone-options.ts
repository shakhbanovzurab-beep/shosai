import { browserTimeZone } from "@/i18n/time-zone";

import { idleChunks } from "./idle-chunks";

/** Пояс в списке выбора: имя IANA для показа, слова, по которым его находит поиск, и смещение от UTC. */
export interface TimeZoneOption {
  zone: string;
  label: string;
  keywords: string[];
  // Слова поиска в нижнем регистре одной строкой: нажатие в поиске не приводит регистр 1 300 раз заново.
  haystack: string;
  // Смещение сейчас, в минутах: без поиска список показывает пояса со смещением браузера.
  offsetMinutes: number;
}

/**
 * Больше строк список не рисует: 420 пунктов cmdk открывались 2,5 с, а символ в поиске стоил до 0,5 с
 * (dev-сборка, CPU ×4) — при цели INP 200 мс. Остальные пояса находит поиск.
 */
export const SHOWN_ZONES = 50;

interface Catalog {
  zones: string[];
  built: Map<string, TimeZoneOption>;
  at: number;
}

const catalogs = new Map<string, Catalog>();
const clocks = new Map<string, Intl.DateTimeFormat>();

/** «America/New_York» → «America/New York». */
export const zoneLabel = (zone: string): string => zone.replaceAll("_", " ");

/*
 * Один форматтер на пояс: его название на языке интерфейса («Москва», «Central European Time») — для поиска,
 * часы и дата в цифрах latn — для смещения. Название берётся на сегодня: в 1970 году Кишинёв жил по московскому.
 */
function option(zone: string, locale: string, at: number): TimeZoneOption {
  const parts = new Intl.DateTimeFormat(locale, {
    timeZone: zone,
    timeZoneName: "longGeneric",
    calendar: "gregory",
    numberingSystem: "latn",
    hourCycle: "h23",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
  }).formatToParts(at);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value;
  const wall = Date.UTC(
    Number(part("year")),
    Number(part("month")) - 1,
    Number(part("day")),
    Number(part("hour")),
    Number(part("minute")),
  );
  const label = zoneLabel(zone);
  const generic = part("timeZoneName");
  const keywords = generic ? [zone, label, generic] : [zone, label];
  return {
    zone,
    label,
    keywords,
    haystack: keywords.join("\n").toLocaleLowerCase(),
    offsetMinutes: Math.round((wall - Math.floor(at / 60_000) * 60_000) / 60_000),
  };
}

function catalog(locale: string): Catalog {
  let found = catalogs.get(locale);
  if (found === undefined) {
    // Браузер перечисляет канонические имена без UTC; его собственный пояс может оказаться старым синонимом.
    const zones = [...new Set([...Intl.supportedValuesOf("timeZone"), "UTC", browserTimeZone()])].sort();
    found = { zones, built: new Map(), at: Date.now() };
    catalogs.set(locale, found);
  }
  return found;
}

function buildOne(state: Catalog, locale: string): boolean {
  const zone = state.zones[state.built.size];
  if (zone === undefined) return false;
  state.built.set(zone, option(zone, locale, state.at));
  // Часы тоже заранее: иначе строки, которые впервые показал поиск, строили бы их во время нажатия.
  zoneClock(zone, locale);
  return true;
}

/**
 * Готовит список порциями, пока браузер простаивает: 420 форматтеров Intl стоили первому открытию 280 мс
 * (CPU ×4 — 920 мс). Зовётся, как только показан раздел; открытие списка достраивает остаток само.
 */
export function prepareTimeZoneOptions(locale: string): () => void {
  const state = catalog(locale);
  return idleChunks(() => buildOne(state, locale));
}

/** Все пояса, которые знает браузер, по алфавиту имён IANA; строятся один раз на язык. */
export function timeZoneOptions(locale: string): ReadonlyMap<string, TimeZoneOption> {
  const state = catalog(locale);
  while (buildOne(state, locale)) {
    // Достраивает то, что не успели порции в простое.
  }
  return state.built;
}

/** Часы пояса на языке интерфейса — «20:51 GMT+3»; форматтер строится, когда строку впервые показали. */
export function zoneClock(zone: string, locale: string): Intl.DateTimeFormat {
  const key = `${locale}|${zone}`;
  let clock = clocks.get(key);
  if (clock === undefined) {
    // Форматтер use-intl не принимает `shortOffset`: свой Intl на языке интерфейса даёт тот же формат.
    clock = new Intl.DateTimeFormat(locale, {
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "shortOffset",
      timeZone: zone,
    });
    clocks.set(key, clock);
  }
  return clock;
}

/**
 * Поиск по вхождению, без учёта регистра: «Москва» находит пояса Москвы, а не всякий, в названии которого
 * встречаются эти буквы вразбивку, как при нечётком поиске cmdk.
 */
export function matchesSearch(option: TimeZoneOption, search: string): boolean {
  return option.haystack.includes(search.trim().toLocaleLowerCase());
}

/**
 * Что показать: без поиска — пояса со смещением браузера и выбранный вручную, с поиском — найденные; не больше
 * `SHOWN_ZONES`. `more` — есть пояса, которых не видно: их находит поиск.
 */
export function shownZones(
  options: ReadonlyMap<string, TimeZoneOption>,
  search: string,
  fixed: string | null,
): { zones: TimeZoneOption[]; more: boolean } {
  const all = [...options.values()];
  const here = options.get(browserTimeZone())?.offsetMinutes;
  const empty = search.trim() === "";
  const found = empty
    ? all.filter((option) => option.offsetMinutes === here || option.zone === fixed)
    : all.filter((option) => matchesSearch(option, search));
  const total = empty ? all.length : found.length;
  return { zones: found.slice(0, SHOWN_ZONES), more: total > Math.min(found.length, SHOWN_ZONES) };
}
