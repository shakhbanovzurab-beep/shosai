import type { MemoryFact, MemoryKind, MemorySource } from "../domain/contract";

/*
 * Что «помнит» Leo в демо: факты разных видов и источников и два кандидата. Живёт в памяти вкладки, как и
 * остальные моки разработки.
 */

const DAY = 86_400_000;
const daysAgo = (days: number) => new Date(Date.now() - days * DAY).toISOString();

const chat: MemorySource = { kind: "user_statement", title: null };
const meeting = (title: string): MemorySource => ({ kind: "meeting", title });

function fact(
  id: string,
  kind: MemoryKind,
  statement: string,
  source: MemorySource,
  days: number,
  extra: Partial<MemoryFact> = {},
): MemoryFact {
  return { id, kind, statement, status: "active", pinned: false, source, created_at: daysAgo(days), ...extra };
}

const SEED: MemoryFact[] = [
  fact("m-01", "preference", "Prefers short answers first, details only when asked", chat, 2, { pinned: true }),
  fact("m-02", "preference", "Writes in English at work and in Russian with family", chat, 12),
  fact("m-03", "fact", "Head of product at Lumen, a team of 14", { kind: "settings", title: null }, 40),
  fact("m-04", "fact", "Based in Moscow; travels to Berlin every other month", chat, 25),
  fact("m-05", "relationship", "Mara Lindqvist leads design and owns the onboarding flow", meeting("Design review"), 6),
  fact("m-06", "relationship", "Jonas Weber is the main contact at Northwind", meeting("Northwind pricing call"), 3),
  fact("m-07", "goal", "Launch the Team plan before the end of November", meeting("Weekly sync with Lumen"), 4, {
    pinned: true,
  }),
  fact("m-08", "goal", "Cut onboarding to under five minutes", { kind: "user_edit", title: null }, 9),
  fact("m-09", "procedure", "Sends release notes to clients every Friday", chat, 18),
  fact("m-10", "procedure", "Keeps meeting notes in the Research folder", chat, 30),
  fact("m-11", "fact", "Has a dentist appointment on Thursday mornings", chat, 1, { status: "candidate" }),
  fact("m-12", "relationship", "Lena prefers async updates over calls", meeting("Retro, sprint 12"), 0, {
    status: "candidate",
  }),
];

const shared = globalThis as typeof globalThis & { memoryFactsDemo?: Map<string, MemoryFact> };
shared.memoryFactsDemo ??= new Map(SEED.map((f) => [f.id, f]));
export const demoFacts = shared.memoryFactsDemo;
