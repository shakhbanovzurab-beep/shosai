import type { Material } from "../domain/contract";
import { decided, fact, material, round, said, step, thread } from "./scenario-build";
import type { StoredFact, StoredThread } from "./types";

/*
 * "Romashka — rollout": the scenario that shows the whole concept. A decision that was reversed while
 * a promise built on the old one is still open; a contract that went in circles three times; an
 * overdue promise; one without a date or an owner; a decision nobody started on; and a promise the
 * user dismissed long ago whose dismissal has run out.
 */

export const ROMASHKA = "romashka";

const intro = "romashka-intro-call";
const kickoff = "romashka-kickoff";
const review = "romashka-interface-review";
const sync0912 = "romashka-sync-0912";
const sync0919 = "romashka-sync-0919";
const rollout = "romashka-rollout-sync";
const sync0926 = "romashka-sync-0926";
const licensing = "romashka-licensing-call";
const sync1003 = "romashka-sync-1003";

export const ROMASHKA_SESSIONS = [intro, kickoff, review, sync0912, sync0919, rollout, sync0926, licensing, sync1003];

export const romashkaThreads = (): StoredThread[] => [
  thread("t-telegram", ROMASHKA, "Telegram integration", {
    stage: "decided",
    owner: "Ivan Petrov",
    gap: { kind: "contradiction", since: "2026-09-24T10:00:00Z" },
    sources: [said(kickoff, 1120), said(review, 1445), said(rollout, 1934)],
    transitions: [
      step(null, "decided", said(kickoff, 1120)),
      step("decided", "in_progress", said(review, 1445)),
      step("in_progress", "decided", said(rollout, 1934)),
    ],
    previousDecision: decided("No Telegram integration", said(kickoff, 1120)),
    decision: decided("Telegram goes into the first release", said(rollout, 1934)),
  }),
  thread("t-contract", ROMASHKA, "Supply contract", {
    stage: "discussed",
    circles: 3,
    owner: "Olga Smirnova",
    sources: [said(sync0912, 702), said(sync0912, 750), said(sync0919, 552), said(sync0926, 365)],
    transitions: [
      step(null, "discussed", said(sync0912, 702), said(sync0912, 750)),
      round(said(sync0919, 552), said(sync0919, 552)),
      round(said(sync0926, 365), said(sync0926, 365)),
    ],
    links: [{ kind: "causes", threadId: "t-team-plan" }],
  }),
  thread("t-sso", ROMASHKA, "SSO access", {
    stage: "in_progress",
    owner: "Ivan Petrov",
    dueAt: "2026-10-05T12:00:00Z",
    gap: { kind: "overdue", since: "2026-10-05T12:00:00Z" },
    sources: [said(sync1003, 510)],
    transitions: [step(null, "in_progress", said(sync1003, 510))],
  }),
  thread("t-pilot-report", ROMASHKA, "Pilot report", {
    stage: "raised",
    gap: { kind: "undated", since: "2026-09-19T10:00:00Z" },
    sources: [said(sync0919, 1300)],
    transitions: [step(null, "raised", said(sync0919, 1300))],
  }),
  thread("t-team-plan", ROMASHKA, "Switch to the Team plan", {
    stage: "decided",
    owner: "Dmitry Volkov",
    gap: { kind: "orphan_decision", since: "2026-09-27T10:00:00Z" },
    sources: [said(licensing, 860)],
    transitions: [step(null, "decided", said(licensing, 860))],
    decision: decided("Romashka switches to the Team plan", said(licensing, 860)),
    links: [{ kind: "blocked_by", threadId: "t-contract" }],
  }),
  thread("t-training", ROMASHKA, "Admin training", {
    stage: "raised",
    owner: "Arham Khan",
    gap: { kind: "forgotten", since: "2026-06-10T10:00:00Z" },
    dismissal: {
      gapKind: "forgotten",
      at: "2026-07-01T09:00:00Z",
      until: "2026-09-29T09:00:00Z",
      by: "human",
      evidence: "",
    },
    sources: [said(intro, 1290)],
    transitions: [step(null, "raised", said(intro, 1290))],
  }),
  thread("t-pilot-users", ROMASHKA, "Pilot user list", {
    stage: "closed",
    owner: "Olga Smirnova",
    sources: [said(sync0919, 980), said(sync1003, 190)],
    transitions: [step(null, "in_progress", said(sync0919, 980)), step("in_progress", "closed", said(sync1003, 190))],
    closedIn: sync1003,
  }),
];

export const romashkaFacts = (): StoredFact[] => [
  fact("f-training", "promise", "Arham runs a training session for Romashka’s admins", said(intro, 1290)),
  fact("f-no-telegram", "decision", "No Telegram integration", said(kickoff, 1120), "f-telegram"),
  fact("f-mockup", "promise", "Ivan prepares the interface mockup without Telegram", said(review, 1445)),
  fact("f-contract-where", "question", "Where are we with the supply contract?", said(sync0912, 702)),
  fact("f-lawyers", "problem", "The contract waits for Romashka’s lawyers", said(sync0912, 750)),
  fact("f-sso-risk", "risk", "If SSO slips, admins can’t log in on launch day", said(sync0912, 1100)),
  fact("f-price", "problem", "The price per seat isn’t agreed", said(sync0919, 552)),
  fact("f-user-list", "promise", "Romashka sends the list of pilot users", said(sync0919, 980)),
  fact("f-report", "promise", "Someone puts together a report on the pilot", said(sync0919, 1300)),
  fact("f-bots", "question", "A separate bot for each department?", said(rollout, 1210)),
  fact("f-telegram", "decision", "Telegram goes into the first release", said(rollout, 1934)),
  fact("f-moved", "problem", "The contract moved to next week again", said(sync0926, 365)),
  fact("f-test-server", "problem", "The test server keeps dropping connections", said(sync0926, 900)),
  fact("f-team-plan", "decision", "Romashka switches to the Team plan", said(licensing, 860)),
  fact("f-sso", "promise", "Ivan sets up SSO access by Monday, Oct 5", said(sync1003, 510)),
];

export const romashkaMaterials = (): Material[] => [
  material("mat-sync-1003", "document", "Summary — Romashka weekly sync", {
    sessionId: sync1003,
    url: `/app/notes/${sync1003}`,
    addedAt: "2026-10-03T10:30:00Z",
  }),
  material("mat-rollout", "document", "Summary — Rollout sync", {
    sessionId: rollout,
    url: `/app/notes/${rollout}`,
    addedAt: "2026-09-24T10:45:00Z",
  }),
  material("mat-plan", "file", "Rollout plan.pdf", {
    sessionId: null,
    url: "https://files.example.com/romashka/rollout-plan.pdf",
    addedAt: "2026-07-20T08:00:00Z",
  }),
  material("mat-contract-draft", "file", "Supply contract — draft 3.docx", {
    sessionId: null,
    url: null,
    addedAt: "2026-09-13T08:00:00Z",
    gone: true,
  }),
];
