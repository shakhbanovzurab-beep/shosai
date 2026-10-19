import type { LeoProposal } from "../domain/proposals";

/*
 * Предложения Leo в демо: два ждут решения с начала (поручение и запрос через MCP), остальные приносит чат.
 * Тексты превью — примеры: настоящий сервер собирает их из ключей i18n и параметров действия.
 */

const HOUR = 3_600_000;
const at = (offset: number) => new Date(Date.now() + offset).toISOString();

const SEED: LeoProposal[] = [
  {
    id: "act-digest",
    tool: "slack.post",
    // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
    title: "Post the weekly digest to #team-updates",
    space: "Lumen",
    origin: { kind: "errand", app: null },
    reversibility: "compensable",
    warning: false,
    taint: null,
    preview: {
      kind: "fields",
      fields: [
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { label: "Channel", value: "#team-updates" },
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { label: "When", value: "Today, 17:00" },
      ],
      body: "This week: pricing agreed with Northwind (€18 per seat, annual). Mara reviews the onboarding copy. Team plan launch stays on track for November.",
    },
    status: "proposed",
    outcome: null,
    created_at: at(-2 * HOUR),
    expires_at: at(3 * HOUR),
    resolved_at: null,
  },
  {
    id: "act-task",
    tool: "tasks.create",
    // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
    title: "Create the task “Review onboarding copy”",
    space: "Lumen",
    origin: { kind: "mcp", app: "Claude Desktop" },
    reversibility: "reversible",
    warning: false,
    taint: null,
    preview: {
      kind: "fields",
      fields: [
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { label: "Board", value: "Launch" },
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { label: "Assignee", value: "Mara Lindqvist" },
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        { label: "Due", value: "Fri, 24 Oct" },
      ],
      body: null,
    },
    status: "proposed",
    outcome: null,
    created_at: at(-HOUR / 2),
    expires_at: at(20 * HOUR),
    resolved_at: null,
  },
];

const shared = globalThis as typeof globalThis & { leoProposalsDemo?: Map<string, LeoProposal> };
shared.leoProposalsDemo ??= new Map(SEED.map((p) => [p.id, p]));
export const demoProposals = shared.leoProposalsDemo;

const OUTCOMES: Record<string, (proposal: LeoProposal, accepted: number) => string> = {
  "mail.send": () => "Sent to jonas.weber@northwind.io",
  "slack.post": () => "Posted to #team-updates",
  "tasks.create": () => "Added to Launch",
  "notes.update": (_, accepted) => `${accepted} ${accepted === 1 ? "change" : "changes"} applied`,
};

/** Решение по предложению: одобренное выполняется, отклонённое закрывается. */
export function decideProposal(id: string, approve: boolean, accepted: number): LeoProposal | null {
  const proposal = demoProposals.get(id);
  if (proposal?.status !== "proposed") return null;
  const decided: LeoProposal = {
    ...proposal,
    status: approve ? "succeeded" : "rejected",
    outcome: approve ? (OUTCOMES[proposal.tool]?.(proposal, accepted) ?? null) : null,
    resolved_at: new Date().toISOString(),
  };
  demoProposals.set(id, decided);
  return decided;
}
