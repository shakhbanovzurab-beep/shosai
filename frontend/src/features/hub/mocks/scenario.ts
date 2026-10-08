import { dayAt } from "./clock";
import { fact, material, said, step, thread, upcoming } from "./scenario-build";
import { ROMASHKA, ROMASHKA_SESSIONS, romashkaFacts, romashkaMaterials, romashkaThreads } from "./scenario-romashka";
import type { Filing, HubDemo, StoredHub } from "./types";

/*
 * The demo, built from an injected "now": Romashka (everything at once), a hiring hub with nothing
 * hanging, a release with no board and no conversations for weeks, an archived pilot, and a recent
 * meeting the server isn't sure about.
 */

const hub = (id: string, name: string, fields: Partial<StoredHub>): StoredHub => ({
  id,
  name,
  kind: "internal",
  boardId: null,
  purpose: null,
  success: null,
  archived: false,
  createdAt: "2026-06-01T09:00:00Z",
  ...fields,
});

const filed = (hubId: string, signal: Filing["signal"]): Filing => ({ hubId, signal });

/** Why each Romashka meeting is filed there: its series, its subject, or its title. */
function romashkaFiling(id: string): [string, Filing] {
  if (id.includes("sync-")) return [id, filed(ROMASHKA, "series")];
  if (id === "romashka-rollout-sync") return [id, filed(ROMASHKA, "subject")];
  return [id, filed(ROMASHKA, "title")];
}

export function seedDemo(now: Date): HubDemo {
  const hubs = [
    hub(ROMASHKA, "Romashka — rollout", {
      kind: "client",
      boardId: "romashka",
      purpose: "Get Romashka into production use",
      success: "Fifty users work in it every day",
      createdAt: "2026-06-08T09:00:00Z",
    }),
    hub("hiring-designer", "Hiring a designer", {
      kind: "pipeline",
      boardId: "work",
      createdAt: "2026-09-20T09:00:00Z",
    }),
    hub("release-2", "Release 2.0", {
      purpose: "Ship 2.0 before the November freeze",
      createdAt: "2026-09-01T09:00:00Z",
    }),
    hub("pilot-alpha", "Pilot Alpha", { kind: "client", boardId: "work", archived: true }),
  ];

  const threads = [
    ...romashkaThreads(),
    thread("t-portfolio", "hiring-designer", "Portfolio review", {
      stage: "closed",
      sources: [said("hiring-design-sync", 240)],
      transitions: [step(null, "in_progress", said("hiring-design-sync", 240))],
      closedIn: "designer-interview-debrief",
    }),
    thread("t-offer", "hiring-designer", "Offer for Lena", {
      stage: "closed",
      owner: "Arham Khan",
      sources: [said("designer-interview-debrief", 300), said("designer-interview-debrief", 820)],
      transitions: [step(null, "closed", said("designer-interview-debrief", 820))],
      closedIn: "designer-interview-debrief",
    }),
    thread("t-scope", "release-2", "Scope freeze for 2.0", {
      stage: "discussed",
      gap: { kind: "silence", since: "2026-09-13T09:00:00Z" },
      sources: [said("release-2-planning", 1500)],
      transitions: [step(null, "discussed", said("release-2-planning", 1500))],
    }),
    thread("t-alpha-results", "pilot-alpha", "Pilot results write-up", {
      stage: "closed",
      sources: [said("pilot-alpha-wrapup", 420)],
      transitions: [step(null, "closed", said("pilot-alpha-wrapup", 420))],
      closedIn: "pilot-alpha-wrapup",
    }),
  ];

  const filings = new Map<string, Filing>([
    ...ROMASHKA_SESSIONS.map(romashkaFiling),
    ["hiring-design-sync", filed("hiring-designer", "title")],
    ["designer-interview-debrief", filed("hiring-designer", "human")],
    ["release-2-planning", filed("release-2", "title")],
    ["pilot-alpha-wrapup", filed("pilot-alpha", "title")],
  ]);

  return {
    hubs: new Map(hubs.map((h) => [h.id, h])),
    threads: new Map(threads.map((t) => [t.id, t])),
    facts: new Map([
      [ROMASHKA, romashkaFacts()],
      [
        "hiring-designer",
        [
          fact("f-portfolio", "promise", "Close the portfolio review by Friday", said("hiring-design-sync", 240)),
          fact("f-salary", "decision", "The salary range is agreed", said("hiring-design-sync", 610)),
          fact("f-offer", "decision", "Make Lena an offer", said("designer-interview-debrief", 300)),
        ],
      ],
      [
        "release-2",
        [fact("f-freeze", "question", "When does the 2.0 scope freeze?", said("release-2-planning", 1500))],
      ],
      ["pilot-alpha", [fact("f-alpha", "promise", "Write up the pilot results", said("pilot-alpha-wrapup", 420))]],
    ]),
    materials: new Map([
      [ROMASHKA, romashkaMaterials()],
      [
        "hiring-designer",
        [
          material("mat-jd", "file", "Product designer — job description", {
            sessionId: null,
            url: "https://files.example.com/hiring/designer-jd.pdf",
            addedAt: "2026-09-20T09:30:00Z",
          }),
        ],
      ],
    ]),
    filings,
    suggestions: new Map([["meeting-oct-05-1718", filed(ROMASHKA, "subject")]]),
    series: new Map(),
    signals: new Map(),
    events: [upcoming("event-romashka-1010", "Romashka weekly sync", dayAt(now, 4, "10:00"), ROMASHKA)],
  };
}
