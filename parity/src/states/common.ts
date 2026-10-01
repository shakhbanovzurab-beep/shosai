// Маркеры и маски, общие для состояний входа и регистрации.

import { withText, type Translate } from "../i18n/texts.ts";
import { ALERT, RESEND_COUNTDOWN } from "../ui/draft-ui.ts";

/** Тост ошибки с текстом перевода. */
export const alert =
  (text: (t: Translate) => string) =>
  (t: Translate): string =>
    withText(ALERT, text(t));

export const loginTitle = (t: Translate): string => withText("h1", t("auth:titleLogin"));

/** Обратный отсчёт повторной отправки кода тикает по настоящим часам. */
export const countdownMask = {
  selectors: () => [RESEND_COUNTDOWN],
  reason: "обратный отсчёт повторной отправки идёт по настоящим часам",
};
