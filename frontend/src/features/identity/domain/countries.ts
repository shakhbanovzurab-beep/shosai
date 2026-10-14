/**
 * Страна, которую человек подтверждает при регистрации, выбирает дом его данных (fr-7, §6): Россия — российский
 * дом, любая другая — европейский. Коды ISO 3166-1 alpha-2 и Косово (XK); названия даёт `Intl.DisplayNames` на
 * языке интерфейса.
 */
// biome-ignore format: таблица кодов читается строками, а не столбцом в 247 строк
export const COUNTRY_CODES = [
  "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AR", "AS", "AT", "AU", "AW", "AX", "AZ", "BA", "BB", "BD", "BE",
  "BF", "BG", "BH", "BI", "BJ", "BL", "BM", "BN", "BO", "BQ", "BR", "BS", "BT", "BW", "BY", "BZ", "CA", "CC", "CD",
  "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN", "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK",
  "DM", "DO", "DZ", "EC", "EE", "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK", "FM", "FO", "FR", "GA", "GB", "GD",
  "GE", "GF", "GG", "GH", "GI", "GL", "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY", "HK", "HN", "HR",
  "HT", "HU", "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR", "IS", "IT", "JE", "JM", "JO", "JP", "KE", "KG", "KH",
  "KI", "KM", "KN", "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS", "LT", "LU", "LV", "LY",
  "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK", "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV",
  "MW", "MX", "MY", "MZ", "NA", "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP", "NR", "NU", "NZ", "OM", "PA", "PE",
  "PF", "PG", "PH", "PK", "PL", "PM", "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW", "SA",
  "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM", "SN", "SO", "SR", "SS", "ST", "SV", "SX", "SY",
  "SZ", "TC", "TD", "TF", "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO", "TR", "TT", "TV", "TW", "TZ", "UA", "UG",
  "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI", "VN", "VU", "WF", "WS", "XK", "YE", "YT", "ZA", "ZM", "ZW",
] as const;

export type CountryCode = (typeof COUNTRY_CODES)[number];

const RUSSIA: CountryCode = "RU";

export const isCountryCode = (value: string): value is CountryCode =>
  (COUNTRY_CODES as readonly string[]).includes(value);

/**
 * Данные россиянина живут в российском доме, а обрабатывает их вычислительный контур в ЕС: для этого нужно
 * отдельное согласие на трансграничную передачу (nfr-14, ID-D2).
 */
export const needsCrossBorderConsent = (country: CountryCode | null): boolean => country === RUSSIA;

/**
 * Страна для подсказки в форме — из регионов языков браузера (`ru-RU` → RU). Только подсказка: человек видит
 * её в поле и может поменять.
 */
export function countryFromLanguages(languages: readonly string[]): CountryCode | null {
  for (const tag of languages) {
    try {
      const region = new Intl.Locale(tag).region;
      if (region !== undefined && isCountryCode(region)) return region;
    } catch {
      // Браузер может отдать тег, который Intl не разбирает: такой язык просто не подсказывает страну.
    }
  }
  return null;
}
