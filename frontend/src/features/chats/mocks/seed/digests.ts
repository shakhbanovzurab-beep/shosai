import { LUMEN } from "@/features/workspace/mocks/demo-lumen";

import type { Binding, Messenger } from "../../domain/contract";
import type { ChatDigest, ChatMessageRef, DigestItem, DigestPromise } from "../../domain/digest-contract";
import type { ChatsDemo } from "../store/types";
import { ago, PRICING_CHAT, project, RELEASE_CHAT, SUPPORT_CHAT } from "./connections";

/*
 * Дайджесты демо — по одному на каждое состояние карточки: полный, период раньше входа бота, сообщения есть,
 * но отметить нечего, сообщений нет. Пункты пишет модель на языке ответа; демо без модели, поэтому они
 * по-английски, как и цитаты, которые написали люди.
 */

const HOUR = 3_600_000;
const DAY = 24 * HOUR;
const inDays = (days: number) => new Date(Date.now() + days * DAY).toISOString().slice(0, 10);

export const RELEASE_DIGEST = "dg-release-week";
export const SUPPORT_DIGEST = "dg-support-week";
export const PRICING_DIGEST = "dg-pricing-week";
export const QUIET_DIGEST = "dg-release-weekend";

function message(url: string | null, n: number, author_name: string, hoursAgo: number, quote: string): ChatMessageRef {
  return { id: `msg-${n}`, author_name, sent_at: ago(hoursAgo * HOUR), quote, url: url ? `${url}/${n}` : null };
}

const item = (id: string, text: string, ref: ChatMessageRef): DigestItem => ({
  id,
  text,
  message: ref,
  proposal_id: null,
  task_id: null,
});

function promise(
  id: string,
  who: DigestPromise["who"],
  text: string,
  due: number | string | null,
  ref: ChatMessageRef,
) {
  const day = typeof due === "number" ? inDays(due) : null;
  return { ...item(id, text, ref), who, due_on: day, when_text: typeof due === "string" ? due : null };
}

const TG = "https://t.me/c/2093847561";

/** Дайджест за дни `[fromDaysAgo, toDaysAgo]` без пунктов; пункты добавляет тот, кто его строит. */
function digest(id: string, chat: ChatDigest["chat"], historyDaysAgo: number, read: number, days = [7, 0]): ChatDigest {
  return {
    id,
    chat,
    period: { from: ago(days[0] * DAY), to: ago(days[1] * DAY) },
    created_at: ago(0),
    coverage: { history_from: ago(historyDaysAgo * DAY), messages_read: read, truncated: false },
    decisions: [],
    questions: [],
    promises: [],
  };
}

/** Чат дайджеста. Название — позиционно: его написали люди. */
const chatRef = (id: string, messenger: Messenger, name: string, binding: Binding): ChatDigest["chat"] => ({
  id,
  workspace_id: LUMEN,
  messenger,
  title: name,
  binding,
});

const release = () => chatRef(RELEASE_CHAT, "telegram", "Release team", project("leo-beta", "Leo beta launch"));

function releaseWeek(): ChatDigest {
  const m = (n: number, who: string, h: number, quote: string) => message(TG, n, who, h, quote);
  return {
    ...digest(RELEASE_DIGEST, release(), 18, 412),
    decisions: [
      item(
        "d1",
        "Leo beta opens to the first 50 customers on Monday, behind the feature flag.",
        m(8812, "Maya Chen", 70, "OK, final: Monday, 50 accounts, flag on. No more scope."),
      ),
      item(
        "d2",
        "The agent steps panel ships without the timeline export; export moves to 2.5.",
        m(8840, "Diego Alvarez", 46, "Let's cut the export from the steps panel, it can wait for 2.5"),
      ),
      item(
        "d3",
        "Onboarding emails go out from the product address, not from personal ones.",
        m(8871, "Sofia Rossi", 20, "Agreed — product@ for all onboarding mail."),
      ),
    ],
    questions: [
      item(
        "q1",
        "Who answers beta customers' questions on the weekend?",
        m(8855, "Diego Alvarez", 30, "who's on call for beta folks this weekend? anyone?"),
      ),
      item(
        "q2",
        "Do the release notes go to the blog or only to the changelog?",
        m(8879, "Sofia Rossi", 9, "blog post or just the changelog this time?"),
      ),
    ],
    promises: [
      promise(
        "p1",
        { user_id: "u-maya", name: "Maya Chen" },
        "Update the release checklist for 2.4",
        2,
        m(8815, "Maya Chen", 68, "I'll update the checklist for 2.4 by Wednesday"),
      ),
      promise(
        "p2",
        { user_id: "u-diego", name: "Diego Alvarez" },
        "Send the beta invite list to support",
        "by Friday",
        m(8846, "Diego Alvarez", 44, "will send the invite list to support by Friday"),
      ),
      promise(
        "p3",
        { user_id: null, name: "Sam from QA" },
        "Run the regression pass on the flagged build",
        1,
        m(8862, "Sofia Rossi", 26, "Sam said he'll do the regression pass tomorrow"),
      ),
      promise(
        "p4",
        { user_id: "u-sofia", name: "Sofia Rossi" },
        "Draft the onboarding email copy",
        null,
        m(8873, "Sofia Rossi", 19, "I'll draft the onboarding copy"),
      ),
    ],
  };
}

function supportWeek(): ChatDigest {
  const chat = chatRef(SUPPORT_CHAT, "telegram", "Support escalations", project("reliability", "Stream reliability"));
  const m = (n: number, who: string, h: number, quote: string) =>
    message(TG.replace("2093847561", "2193004417"), n, who, h, quote);
  return {
    ...digest(SUPPORT_DIGEST, chat, 3, 48),
    questions: [
      item(
        "q1",
        "Is the dropped-answer bug in Safari the same as last week's?",
        m(311, "Noah Kim", 30, "is the safari dropped answer thing the same bug as last week?"),
      ),
    ],
    promises: [
      promise(
        "p1",
        { user_id: "u-noah", name: "Noah Kim" },
        "Add a heartbeat alert for long answers",
        3,
        m(318, "Noah Kim", 22, "I'll add an alert on the heartbeat gap"),
      ),
    ],
  };
}

export function seedDigests(demo: ChatsDemo) {
  const pricing = chatRef(PRICING_CHAT, "slack", "pricing", project("pricing", "Team plan pricing"));
  for (const value of [
    releaseWeek(),
    supportWeek(),
    digest(PRICING_DIGEST, pricing, 12, 23),
    digest(QUIET_DIGEST, release(), 18, 0, [10, 8]),
  ])
    demo.digests.set(value.id, value);
}
