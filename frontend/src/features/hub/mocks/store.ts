import { listBoards } from "@/features/kanban/mocks/demo-store";

import { demoNow } from "./clock";
import { seedDemo } from "./scenario";
import { chronological } from "./sessions";
import type { HubDemo, StoredHub, StoredThread } from "./types";

/* The in-memory Hub for the demo, used when BACKEND_API_URL is unset; resets on restart. */

const shared = globalThis as typeof globalThis & { hubDemo?: HubDemo };
shared.hubDemo ??= seedDemo(demoNow());
export const demo = shared.hubDemo;

export const findHub = (id: string) => demo.hubs.get(id) ?? null;

export const findThread = (id: string) => {
  const thread = demo.threads.get(id);
  return thread && demo.hubs.has(thread.hubId) ? thread : null;
};

export const threadsOf = (hubId: string): StoredThread[] => [...demo.threads.values()].filter((t) => t.hubId === hubId);

/** The meetings filed in a hub, oldest first. */
export const sessionsOf = (hubId: string) =>
  chronological([...demo.filings].filter(([, filing]) => filing.hubId === hubId).map(([id]) => id));

export const factsOf = (hubId: string) => demo.facts.get(hubId) ?? [];

export const materialsOf = (hubId: string) => demo.materials.get(hubId) ?? [];

/** A board's name, or null when there is no such board any more. */
export const boardName = (boardId: string | null) =>
  boardId === null ? null : (listBoards().find((b) => b.id === boardId)?.name ?? null);

export const boardExists = (boardId: string) => listBoards().some((b) => b.id === boardId);

export const MAX_HUBS = 50;

export function addHub(name: string): StoredHub {
  const created: StoredHub = {
    id: `hub-${crypto.randomUUID().slice(0, 8)}`,
    name,
    kind: "internal",
    boardId: null,
    purpose: null,
    success: null,
    archived: false,
    createdAt: new Date().toISOString(),
  };
  demo.hubs.set(created.id, created);
  return created;
}

/** Deletes the hub and its addressing; the meetings, tasks and documents stay where they are. */
export function deleteHub(id: string) {
  demo.hubs.delete(id);
  for (const thread of threadsOf(id)) demo.threads.delete(thread.id);
  for (const [session, filing] of demo.filings) if (filing.hubId === id) demo.filings.delete(session);
  for (const [session, filing] of demo.suggestions) if (filing.hubId === id) demo.suggestions.delete(session);
  for (const [series, hubId] of demo.series) if (hubId === id) demo.series.delete(series);
  demo.facts.delete(id);
  demo.materials.delete(id);
  demo.events = demo.events.filter((event) => event.hubId !== id);
}

export const nameTaken = (name: string, except: string | null = null) =>
  [...demo.hubs.values()].some((h) => h.id !== except && h.name.toLocaleLowerCase() === name.toLocaleLowerCase());
