/* Языки интерфейса кабинета в кодах Excalidraw: доска говорит на языке человека (meetings A11). */

const EXCALIDRAW_LANGUAGES: Readonly<Record<string, string>> = {
  en: "en",
  ru: "ru-RU",
  ar: "ar-SA",
  de: "de-DE",
  es: "es-ES",
  fr: "fr-FR",
  hi: "hi-IN",
  id: "id-ID",
  it: "it-IT",
  ja: "ja-JP",
  ko: "ko-KR",
  nl: "nl-NL",
  "pt-BR": "pt-BR",
  tr: "tr-TR",
  vi: "vi-VN",
  "zh-Hant": "zh-TW",
};

/** Код языка Excalidraw для языка кабинета; незнакомый — английский. */
export const boardLanguage = (language: string) => EXCALIDRAW_LANGUAGES[language] ?? "en";
