"use client";

import { useResponseLanguageSetting } from "@/features/settings/model/leo-settings";
import { useUiLanguage } from "@/hooks/use-ui-language";

import { answerLanguage } from "../domain/answer-language";

/** The language Leo's answers are written in, as the server decides it: see `answerLanguage`. */
export function useLeoAnswerLanguage() {
  return answerLanguage(useResponseLanguageSetting(), useUiLanguage());
}
