/**
 * Memory API contract: what Leo remembers about the person (ADR 0030, Leo architecture §7.2), on the
 * routes of Leo architecture §13.2. The backend's `memory` slice is not built yet; until it is, the
 * development mocks answer the same `/v1` paths. See docs/memory-api.md.
 *
 * GET    /v1/agent/memory?cursor=       → FactsPage   (candidates and active facts; forgotten ones are never listed)
 * PATCH  /v1/agent/memory/{id}          → MemoryFact  (FactUpdate; a new statement supersedes, so the answer has a new id)
 * POST   /v1/agent/memory/{id}/accept   → MemoryFact  (a candidate becomes active)
 * DELETE /v1/agent/memory/{id}          → 204         (forgets a fact, or turns a candidate down)
 * DELETE /v1/agent/memory               → 204         (forgets everything)
 */

/** Preference, fact, relationship (people), goal, procedure (how the person works). */
export const MEMORY_KINDS = ["preference", "fact", "relationship", "goal", "procedure"] as const;
export type MemoryKind = (typeof MEMORY_KINDS)[number];

/** Where a fact came from: the person said it in a chat, a meeting, Settings, or the person edited it. */
export const SOURCE_KINDS = ["user_statement", "meeting", "settings", "user_edit"] as const;
export type SourceKind = (typeof SOURCE_KINDS)[number];

/** Every fact shows its source; `title` names the meeting for `meeting` and is null otherwise. */
export type MemorySource = { kind: SourceKind; title: string | null };

export type MemoryFact = {
  id: string;
  kind: MemoryKind;
  /** In the person's language; it is the person's data, shown as written (`dir="auto"`). */
  statement: string;
  /** A candidate waits for "Should Leo remember this?" and is not used in answers until accepted. */
  status: "candidate" | "active";
  /** Pinned facts are always part of Leo's profile of the person. */
  pinned: boolean;
  source: MemorySource;
  created_at: string;
};

export type FactsPage = { facts: MemoryFact[]; next_cursor: string | null };

export type FactUpdate = { statement?: string; pinned?: boolean };

export const STATEMENT_MAX = 500;
