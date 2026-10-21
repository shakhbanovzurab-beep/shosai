/*
 * Даты карточек пользователей — в деловом поясе платформы (ADR 0058): в нём сервер считает и расходы на ИИ, что
 * показывает карточка. Время дня подписано поясом («МСК»); пояс и подпись дают вызывающие.
 */

const dateFormats = new Map<string, Intl.DateTimeFormat>();
const dateTimeFormats = new Map<string, Intl.DateTimeFormat>();

function cached(cache: Map<string, Intl.DateTimeFormat>, zone: string, options: Intl.DateTimeFormatOptions) {
  let format = cache.get(zone);
  if (format === undefined) {
    format = new Intl.DateTimeFormat("ru-RU", { ...options, timeZone: zone });
    cache.set(zone, format);
  }
  return format;
}

/** Пояс, в котором показываются даты, и его подпись рядом со временем. */
export interface DisplayZone {
  zone: string;
  label: string;
}

const usdFormat = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

export const formatDate = (iso: string, { zone }: DisplayZone) =>
  cached(dateFormats, zone, { day: "numeric", month: "short", year: "numeric" }).format(new Date(iso));

export const formatDateTime = (iso: string, { zone, label }: DisplayZone) =>
  `${cached(dateTimeFormats, zone, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso))} ${label}`;

/** Сумма расходов на ИИ: сервер присылает доллары строкой, без потери точности. */
export const formatUsd = (amount: string) => usdFormat.format(Number(amount));
