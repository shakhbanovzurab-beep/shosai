import { PRICING_CHAT, RELEASE_CHAT, SUPPORT_CHAT } from "@/features/chats/mocks/seed/connections";
import { PRICING_DIGEST, QUIET_DIGEST, RELEASE_DIGEST, SUPPORT_DIGEST } from "@/features/chats/mocks/seed/digests";
import { LUMEN } from "@/features/workspace/mocks/demo-lumen";

import type { Scenario } from "./demo-scenarios";

/*
 * «Пройдись по чату #release за неделю» в демо: шаг чтения чата, артефакт `chat_digest` (CF-D11) и короткий
 * ответ. Какой дайджест — по названию чата в вопросе: у каждого своё состояние карточки (полный, раньше входа
 * бота, нечего отметить, сообщений нет). Тексты ответа пишет модель на языке ответа; демо — по-английски.
 */

type DigestCase = { chat: string; digest: string; chatName: string; answer: string };

const CASES: [RegExp, DigestCase][] = [
  [
    /\bsupport\b/i,
    {
      chat: SUPPORT_CHAT,
      digest: SUPPORT_DIGEST,
      chatName: "Support escalations",
      answer:
        "Here’s what mattered in Support escalations. I joined that chat three days ago, so the week starts there.",
    },
  ],
  [
    /\bpricing\b/i,
    {
      chat: PRICING_CHAT,
      digest: PRICING_DIGEST,
      chatName: "#pricing",
      answer: "I read #pricing for the week: people talked, but nothing was decided, asked or promised.",
    },
  ],
  [
    /\bweekend\b/i,
    {
      chat: RELEASE_CHAT,
      digest: QUIET_DIGEST,
      chatName: "Release team",
      answer: "Release team was quiet then: no messages in that period.",
    },
  ],
];

const RELEASE: DigestCase = {
  chat: RELEASE_CHAT,
  digest: RELEASE_DIGEST,
  chatName: "Release team",
  answer:
    "Here’s the week in Release team: three decisions, two open questions and seven agreements. Make any of them a task and I’ll prepare it for your approval.",
};

function scenarioOf(found: DigestCase): Scenario {
  return {
    steps: [{ action: "read_chat", detail: found.chatName, result: "Read the period", ms: 1_100 }],
    artifact: () => ({
      kind: "chat_digest",
      ref: found.digest,
      // i18n-ignore: демо-данные; подпись артефакта сервер пишет на языке человека
      alt: `Digest of ${found.chatName}`,
      workspace_id: LUMEN,
      chat_id: found.chat,
    }),
    answer: found.answer,
  };
}

// Демо без модели: просьба о дайджесте узнаётся по словам английского вопроса.
const ASKS_FOR_DIGEST = /\b(digest|go through|went through|summari[sz]e the chat)\b/i;

export function digestScenario(question: string): Scenario | null {
  if (!ASKS_FOR_DIGEST.test(question)) return null;
  return scenarioOf(CASES.find(([pattern]) => pattern.test(question))?.[1] ?? RELEASE);
}
