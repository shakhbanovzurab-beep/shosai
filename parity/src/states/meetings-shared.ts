// Публичная страница итога встречи /r/:token (шаг 4): итог, загрузка, пароль,
// недействительная ссылка, обсуждение. Ссылки и комментарии засеяны.

import type { Page } from "@playwright/test";

import { exactText, type Translate } from "../i18n/texts.ts";
import { SEED_IDS } from "../recording/seed-ids.ts";
import { hold, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const SHARED = "/v1/meetings/shared/{token}";
const budgetTitle = (): string => 'h1:has-text("Планирование бюджета Q4")';

async function submitPassword(page: Page, { t }: StateContext, password: string): Promise<void> {
  await page.getByLabel(t("meetings:sharedMeeting.password")).fill(password);
  await page.getByRole("button", { name: t("meetings:sharedMeeting.open") }).click();
}

function shared(id: string, fixture: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `meetings.shared.${id}`, fixture: `meetings/${fixture}`, scope: "single", marker, ...extra };
}

export const MEETINGS_SHARED_STATES: readonly State[] = [
  shared("populated", "shared", budgetTitle, { scope: "full" }),
  shared("loading", "shared", () => ".shr svg.spin", { overrides: [hold("GET", SHARED)] }),
  shared("password", "shared-locked", (t) => exactText(t("meetings:sharedMeeting.locked")), { scope: "full" }),
  shared("password-wrong", "shared-locked", (t) => exactText(t("meetings:sharedMeeting.wrong")), {
    act: async (page, context) => submitPassword(page, context, "wrong-pass"),
  }),
  shared("unlocked", "shared-unlocked", () => 'h1:has-text("Звонок с юристом по договору")', {
    act: async (page, context) => submitPassword(page, context, SEED_IDS.sharePassword),
  }),
  shared("gone", "shared-gone", (t) => exactText(t("meetings:sharedMeeting.gone")), { scope: "full" }),
  shared("comments-closed", "shared-closed", (t) => exactText(t("meetings:sharedMeeting.commentsClosed")), { reveal: true }),
  shared("transcript-truncated", "shared", (t) => exactText(t("meetings:sharedMeeting.transcriptTruncated")), {
    reveal: true,
    overrides: [{ method: "GET", path: SHARED, respond: { merge: { transcript_truncated: true } },
      reason: "стенограмма длиннее 500 реплик: та же встреча, обрезка — по флагу ответа" }],
  }),
  shared("comments-truncated", "shared", (t) => exactText(t("meetings:sharedMeeting.commentsTruncated", { total: 240 })), {
    reveal: true,
    overrides: [{ method: "GET", path: SHARED, respond: { merge: { comments: { total: 240 } } },
      reason: "обсуждение длиннее 200 реплик: та же встреча, всего — по счётчику ответа" }],
  }),
  shared("comment-failed", "shared", (t) => exactText(t("meetings:sharedMeeting.commentFailed")), {
    overrides: [serverError("POST", `${SHARED}/comments`)],
    act: async (page, { t }) => {
      await page.getByLabel(t("meetings:sharedMeeting.yourName")).fill("Гость");
      await page.getByLabel(t("meetings:sharedMeeting.yourComment")).fill("Спасибо за итоги!");
      await page.getByRole("button", { name: t("meetings:sharedMeeting.send"), exact: true }).click();
    },
  }),
];
