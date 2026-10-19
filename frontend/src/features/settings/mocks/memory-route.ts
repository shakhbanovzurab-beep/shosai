import { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import { type MemorySummary, SUMMARY_MESSAGE_MAX } from "../domain/memory-contract";
import { addSummaryNote, getSummary, refreshSummary } from "./demo-settings";
import { readJson, refuse } from "./problems";
import { notesTitle } from "./summary-words";

/** /api/settings/memories/summary */
export const memorySummaryRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<MemorySummary>(getSummary(await notesTitle()));
  },

  /** "Ask or update": a question about the summary, or something to remember or forget. */
  async POST(request: Request) {
    const body = z
      .object({ message: z.string().trim().min(1).max(SUMMARY_MESSAGE_MAX) })
      .safeParse(await readJson(request));
    if (!body.success) return refuse("summaryMessageRequired", 422);
    addSummaryNote(body.data.message);
    return JsonResponse.json<MemorySummary>(getSummary(await notesTitle()));
  },
};

/** /api/settings/memories/summary/refresh */
export const memorySummaryRefreshRoute = {
  /** Rewrites the summary from the latest memories and chats. */
  async POST(_request: Request) {
    refreshSummary();
    return JsonResponse.json<MemorySummary>(getSummary(await notesTitle()));
  },
};
