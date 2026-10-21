import type { Person } from "../../domain/tasks-contract";
import type { KanbanDemo } from "../store/types";
import { DIEGO, ELENA, gradientPreview, MAYA, ME_PERSON, seedAttachment, seedComment, seedSubtasks } from "./builders";

/* Подзадачи, комментарии и вложения доски «Work»; у бага SSO длинная ветка, чтобы видно было «Показать ранее». */

const SSO_THREAD: [author: Person, body: string, minutesAgo: number][] = [
  [ELENA, "Only with the Okta tenant so far.", 2_900],
  [ME_PERSON, "Which browsers? I can't reproduce it in Chrome.", 2_880],
  [ELENA, "Safari 18 and the iOS app's web view.", 2_850],
  [DIEGO, "Same here on Safari. Firefox is fine.", 2_700],
  [ME_PERSON, "Looks like the third-party cookie block. The redirect loses the state cookie.", 2_600],
  [MAYA, "Can we keep the state in the URL instead?", 2_500],
  [
    ME_PERSON,
    "Yes, signed. Okta allows it: https://developer.okta.com/docs/guides/implement-grant-type/authcode/main/",
    2_400,
  ],
  [ELENA, "The customer asks for a date. Is Friday realistic?", 1_400],
  [ME_PERSON, "Friday for the fix, Monday for their tenant after QA.", 1_380],
  [DIEGO, "I'll test it on my iPhone once it's on staging.", 600],
  [ELENA, "Thanks! I told them Monday.", 300],
  [ME_PERSON, "Fix is on staging.", 90],
];

export function seedWorkThreads(demo: KanbanDemo) {
  demo.subtasks.set(
    "w-schema",
    seedSubtasks("w-schema", [
      ["Parties and employees", true],
      ["Tenders and work orders", true],
      ["Indexes for search", false],
    ]),
  );
  demo.subtasks.set(
    "w-sso-crash",
    seedSubtasks("w-sso-crash", [
      ["Reproduce", true],
      ["Fix the redirect", false],
    ]),
  );
  demo.comments.set("w-schema", [
    seedComment("w-schema-c1", MAYA, "Should work orders keep their history?", 300),
    seedComment("w-schema-c2", ME_PERSON, "Yes, as a separate table. See https://orm.drizzle.team", 240),
  ]);
  demo.comments.set(
    "w-sso-crash",
    SSO_THREAD.map(([author, body, ago], index) => seedComment(`w-sso-crash-c${index + 1}`, author, body, ago)),
  );
  demo.attachments.set("w-schema", [
    seedAttachment("w-schema-a1", "schema.png", 412_000, ME_PERSON, gradientPreview("#6366f1", "#0ea5e9")),
    seedAttachment("w-schema-a2", "Data model.pdf", 1_240_000, MAYA, null),
  ]);
  demo.attachments.set("w-sso-crash", [
    seedAttachment("w-sso-crash-a1", "safari-console.png", 230_000, ELENA, gradientPreview("#f43f5e", "#f59e0b")),
  ]);
}
