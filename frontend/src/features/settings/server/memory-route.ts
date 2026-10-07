import { NextResponse } from "next/server";

import { z } from "zod";

import { forwardToBackend } from "@/server/backend-proxy";

import { type MemoriesResponse, type MemorySummary, SUMMARY_MESSAGE_MAX } from "../domain/memory-contract";
import { addSummaryNote, clearMemories, deleteMemory, getSummary, listMemories, refreshSummary } from "./demo-settings";
import { readJson, refuse } from "./problems";
import { notesTitle } from "./summary-words";

const MEMORIES_PATH = "/v1/settings/memories";
const SUMMARY_PATH = "/v1/settings/memories/summary";

/** /api/settings/memories */
export const memoriesRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, MEMORIES_PATH);
    if (upstream) return upstream;
    return NextResponse.json<MemoriesResponse>({ memories: listMemories() });
  },

  /** Forgets everything. */
  async DELETE(request: Request) {
    const upstream = await forwardToBackend(request, MEMORIES_PATH);
    if (upstream) return upstream;
    clearMemories();
    return new Response(null, { status: 204 });
  },
};

/** /api/settings/memories/[id] */
export const memoryRoute = {
  async DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `${MEMORIES_PATH}/${encodeURIComponent(id)}`);
    if (upstream) return upstream;
    return deleteMemory(id) ? new Response(null, { status: 204 }) : refuse("memoryNotFound", 404);
  },
};

/** /api/settings/memories/summary */
export const memorySummaryRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, SUMMARY_PATH);
    if (upstream) return upstream;
    return NextResponse.json<MemorySummary>(getSummary(await notesTitle()));
  },

  /** "Ask or update": a question about the summary, or something to remember or forget. */
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, SUMMARY_PATH);
    if (upstream) return upstream;
    const body = z
      .object({ message: z.string().trim().min(1).max(SUMMARY_MESSAGE_MAX) })
      .safeParse(await readJson(request));
    if (!body.success) return refuse("summaryMessageRequired", 422);
    addSummaryNote(body.data.message);
    return NextResponse.json<MemorySummary>(getSummary(await notesTitle()));
  },
};

/** /api/settings/memories/summary/refresh */
export const memorySummaryRefreshRoute = {
  /** Rewrites the summary from the latest memories and chats. */
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, `${SUMMARY_PATH}/refresh`);
    if (upstream) return upstream;
    refreshSummary();
    return NextResponse.json<MemorySummary>(getSummary(await notesTitle()));
  },
};
