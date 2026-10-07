/* ---------- Memory: GET|DELETE /settings/memories, DELETE /settings/memories/{id} ---------- */

export type Memory = { id: string; text: string; created_at: string };
export type MemoriesResponse = { memories: Memory[] };

/*
 * ---------- Memory summary ----------
 * GET /settings/memories/summary, POST /settings/memories/summary (ask or update),
 * POST /settings/memories/summary/refresh
 */

/** An overview of what Leo has learned, written by the model from memories and chats, like ChatGPT's. */
export type MemorySummary = {
  sections: { title: string; body: string }[];
  /** Questions the user might ask about it ("Learn more"). */
  suggestions: string[];
  updated_at: string | null;
};

/** Asks about the summary or tells Leo what to change ("Forget that I…", "I moved to…"). */
export type MemorySummaryMessage = { message: string };
export const SUMMARY_MESSAGE_MAX = 2000;
