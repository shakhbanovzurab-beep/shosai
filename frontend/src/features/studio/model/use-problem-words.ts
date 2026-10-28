import { useTranslations } from "use-intl";

import type { ProblemWords } from "./studio-problem-words";

/** Переводчики, которыми действия Studio называют отказы сервера. */
export function useProblemWords(): ProblemWords {
  return { api: useTranslations("studioApi"), studio: useTranslations("studio") };
}
