// Intl.DurationFormat (ES2025): в lib TypeScript 5.9 его ещё нет — описано то, чем пользуется кабинет.
// biome-ignore lint/style/noNamespace: глобальный Intl — пространство имён, дополнить его можно только так.
declare namespace Intl {
  type DurationFormatPart = "days" | "hours" | "minutes" | "seconds";

  interface DurationFormatOptions {
    style?: "long" | "short" | "narrow" | "digital";
    hoursDisplay?: "always" | "auto";
    minutesDisplay?: "always" | "auto";
    secondsDisplay?: "always" | "auto";
  }

  class DurationFormat {
    constructor(locales?: string | readonly string[], options?: DurationFormatOptions);
    format(duration: Partial<Record<DurationFormatPart, number>>): string;
  }
}
