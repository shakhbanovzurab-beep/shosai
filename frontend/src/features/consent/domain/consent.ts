// Согласие человека на cookie аналитики и рекламы (ADR 0047): одно решение на обе цели. Хранится в
// first-party cookie, общей с публичным сайтом на том же домене: спрашивает сайт, кабинет не
// спрашивает, а только читает выбор и даёт изменить его в настройках.

export type ConsentChoice = "granted" | "denied";

/** Сигналы Consent Mode v2, которые решает выбор человека. */
export type ConsentSignals = Record<
  "ad_storage" | "analytics_storage" | "ad_user_data" | "ad_personalization",
  ConsentChoice
>;

export const CONSENT_COOKIE = "shosai_consent";
// Полгода: выбор не переспрашивают чаще, но и не держат бессрочно.
export const CONSENT_DAYS = 180;
// Версия формата: новое значение спросит человека заново, а не прочтёт старое неверно.
const FORMAT = "v1";

export function encodeConsent(choice: ConsentChoice): string {
  return `${FORMAT}.${choice}`;
}

/** Выбор из значения cookie; null — человек ещё не решал или значение чужого формата. */
export function decodeConsent(value: string | null): ConsentChoice | null {
  if (value === encodeConsent("granted")) return "granted";
  if (value === encodeConsent("denied")) return "denied";
  return null;
}

export function consentSignals(choice: ConsentChoice): ConsentSignals {
  return { ad_storage: choice, analytics_storage: choice, ad_user_data: choice, ad_personalization: choice };
}

const CONTAINER_ID = /^GTM-[A-Z0-9]{4,12}$/;

/** Идентификатор контейнера GTM из настроек сборки; пустой или чужой формы — GTM выключен. */
export function containerIdFrom(value: string | undefined): string | null {
  const id = value?.trim() ?? "";
  return CONTAINER_ID.test(id) ? id : null;
}
