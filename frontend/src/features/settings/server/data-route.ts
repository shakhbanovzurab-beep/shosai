import { NextResponse } from "next/server";

import { exportStudioData } from "@/features/studio/server";
import { forwardToBackend } from "@/server/backend-proxy";

import { type DataItemsResponse, isDataKind } from "../domain/data-contract";
import { deleteAll, deleteItem, listItems } from "./demo-data";
import { listServers } from "./demo-mcp";
import { getSettings, getSummary } from "./demo-settings";
import { refuse } from "./problems";
import { notesTitle } from "./summary-words";

type KindContext = { params: Promise<{ kind: string }> };

/** /api/settings/data/[kind] */
export const dataKindRoute = {
  async GET(request: Request, { params }: KindContext) {
    const { kind } = await params;
    const upstream = await forwardToBackend(request, `/v1/settings/data/${encodeURIComponent(kind)}`);
    if (upstream) return upstream;
    if (!isDataKind(kind)) return refuse("dataKindUnknown", 404);
    return NextResponse.json<DataItemsResponse>({ items: listItems(kind) });
  },

  /** Deletes every item of the kind: unshares all links, removes all files or all feedback. */
  async DELETE(request: Request, { params }: KindContext) {
    const { kind } = await params;
    const upstream = await forwardToBackend(request, `/v1/settings/data/${encodeURIComponent(kind)}`);
    if (upstream) return upstream;
    if (!isDataKind(kind)) return refuse("dataKindUnknown", 404);
    deleteAll(kind);
    return new Response(null, { status: 204 });
  },
};

/** /api/settings/data/[kind]/[id] */
export const dataItemRoute = {
  async DELETE(request: Request, { params }: { params: Promise<{ kind: string; id: string }> }) {
    const { kind, id } = await params;
    const upstream = await forwardToBackend(
      request,
      `/v1/settings/data/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`,
    );
    if (upstream) return upstream;
    if (!isDataKind(kind)) return refuse("dataKindUnknown", 404);
    return deleteItem(kind, id) ? new Response(null, { status: 204 }) : refuse("dataItemNotFound", 404);
  },
};

/** /api/settings/data/export */
export const dataExportRoute = {
  /**
   * Downloads everything we hold about the user as one file. The backend streams a full archive; the
   * demo bundles what it keeps in memory as JSON (secrets such as MCP auth headers are never included).
   */
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/settings/data/export");
    if (upstream) return upstream;
    const exported = {
      exported_at: new Date().toISOString(),
      settings: getSettings(),
      memory_summary: getSummary(await notesTitle()),
      mcp_servers: listServers(),
      studio: exportStudioData(),
      shared_chats: listItems("shared_chats"),
      shared_artifacts: listItems("shared_artifacts"),
      uploaded_files: listItems("uploaded_files"),
      feedback: listItems("feedback"),
    };
    const date = exported.exported_at.slice(0, 10);
    return new Response(JSON.stringify(exported, null, 2), {
      headers: {
        "content-type": "application/json; charset=utf-8",
        "content-disposition": `attachment; filename="data-export-${date}.json"`,
      },
    });
  },
};
