import type { LeoActionId } from "../domain/actions";
import type { LeoArtifact } from "../domain/artifacts";
import type { LeoProposal } from "../domain/proposals";
import type { LeoSource } from "../domain/sources";
import { digestScenario } from "./digest-scenario";

/*
 * Три сценария демо-агента, чтобы увидеть новые блоки: ответ с источниками (Cited Answer), письмо на одобрение
 * (Approval Card) и правка заметки с пословным сравнением (Inline Diff). Тексты — примеры по демо-данным
 * кабинета (Lumen, Northwind); настоящая модель пишет их сама на языке ответа.
 */

export interface PlannedStep {
  action: LeoActionId;
  detail?: string;
  result?: string;
  ms: number;
}

export type Scenario = {
  steps: PlannedStep[];
  sources?: LeoSource[];
  proposal?: () => LeoProposal;
  /** Результат, который карточка читает по ссылке: дайджест чата. */
  artifact?: () => LeoArtifact;
  answer: string;
};

const HOUR = 3_600_000;

function proposal(fields: Pick<LeoProposal, "tool" | "title" | "space" | "reversibility" | "taint" | "preview">) {
  return (): LeoProposal => ({
    id: `act-${crypto.randomUUID()}`,
    origin: { kind: "thread", app: null },
    warning: false,
    status: "proposed",
    outcome: null,
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + HOUR).toISOString(),
    resolved_at: null,
    ...fields,
  });
}

const CITED: Scenario = {
  steps: [
    { action: "search_meetings", detail: "Northwind pricing", result: "3 meetings", ms: 900 },
    { action: "search_mail", detail: "Jonas Weber", result: "2 emails", ms: 800 },
  ],
  sources: [
    {
      id: "src-call",
      kind: "meeting",
      // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
      title: "Northwind pricing call",
      space: "Lumen",
      locator: "18:42",
      quote: "Jonas: we can sign at eighteen euros per seat if the annual plan includes onboarding for both teams.",
      highlight: ["eighteen euros per seat", "onboarding for both teams"],
    },
    {
      id: "src-mail",
      kind: "mail",
      // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
      title: "Re: Pricing follow-up",
      space: "Personal",
      locator: null,
      quote: "Confirming what we discussed: billing starts on 1 March and is invoiced yearly in advance.",
      highlight: ["billing starts on 1 March", "invoiced yearly in advance"],
    },
    {
      id: "src-note",
      kind: "note",
      // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
      title: "Weekly sync — notes",
      space: "Lumen",
      locator: null,
      quote: "Open question: Mara checks whether onboarding fits into the first two weeks.",
      highlight: ["onboarding fits into the first two weeks"],
    },
  ],
  answer: [
    "You agreed with Northwind on €18 per seat on the annual plan, with onboarding for both teams included [1]. Billing starts on 1 March and is invoiced yearly in advance [2].",
    "",
    "One thing is still open: Mara is checking whether onboarding fits into the first two weeks [3].",
  ].join("\n"),
};

const FOLLOW_UP: Scenario = {
  steps: [
    { action: "search_meetings", detail: "Northwind pricing call", result: "Found", ms: 800 },
    { action: "draft_email", detail: "Follow-up to Jonas Weber", result: "Draft ready", ms: 1100 },
    { action: "send_email", detail: "jonas.weber@northwind.io", result: "Waiting for you", ms: 400 },
  ],
  proposal: proposal({
    tool: "mail.send",
    // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
    title: "Send the follow-up to Jonas Weber",
    space: "Personal",
    reversibility: "irreversible",
    taint: "Prepared using an email from jonas.weber@northwind.io",
    preview: {
      kind: "fields",
      fields: [
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { label: "To", value: "Jonas Weber <jonas.weber@northwind.io>" },
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { label: "Subject", value: "Northwind × Lumen — what we agreed" },
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { label: "From", value: "arham@lumen.so" },
      ],
      body: "Hi Jonas,\n\nThanks for the call today. As agreed: €18 per seat on the annual plan, onboarding for both teams included, billing from 1 March, invoiced yearly.\n\nI’ll send the contract by Friday.\n\nBest,\nArham",
    },
  }),
  answer: "I drafted the follow-up from today’s call. Check it below: I’ll send it only after you approve.",
};

const SHORTER: Scenario = {
  steps: [{ action: "search_files", detail: "Weekly sync — notes", result: "Found", ms: 800 }],
  proposal: proposal({
    tool: "notes.update",
    // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
    title: "Update “Weekly sync — notes”",
    space: "Lumen",
    reversibility: "reversible",
    taint: null,
    preview: {
      kind: "diff",
      target: "Weekly sync — notes",
      segments: [
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { type: "equal", text: "We " },
        { type: "change", remove: "are planning to", insert: "will" },
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { type: "equal", text: " launch the Team plan " },
        { type: "change", remove: "at some point before the end of", insert: "before" },
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { type: "equal", text: " November. Mara " },
        { type: "change", remove: "is going to take a look at", insert: "reviews" },
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { type: "equal", text: " the onboarding copy" },
        { type: "change", remove: " and will see whether it can be made shorter", insert: "" },
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { type: "equal", text: ". Jonas " },
        { type: "change", remove: "said that Northwind would", insert: "will" },
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { type: "equal", text: " sign once onboarding is included." },
      ],
    },
  }),
  answer: "Here’s a tighter version of your note. Take the changes you want: nothing changes until you apply them.",
};

// Демо без модели: сценарий выбирается по словам английского вопроса; на всё остальное отвечает обычная заглушка.
const RULES: [RegExp, Scenario][] = [
  [/\b(follow[- ]?up|send)\b/i, FOLLOW_UP],
  [/\b(shorter|shorten|tighten|rewrite)\b/i, SHORTER],
  [/\b(agree|agreed|pricing)\b/i, CITED],
];

export const pickScenario = (question: string): Scenario | null =>
  digestScenario(question) ?? RULES.find(([pattern]) => pattern.test(question))?.[1] ?? null;
