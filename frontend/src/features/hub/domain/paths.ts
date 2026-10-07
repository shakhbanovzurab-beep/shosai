/* Addresses in the Hub. A topic opens over its hub's page with `?open=<id>`, so it has a link of its own. */

const e = encodeURIComponent;

export const HUBS_PATH = "/app/hub";

export const hubPath = (hubId: string) => `${HUBS_PATH}/${e(hubId)}`;

export const OPEN_PARAM = "open";

export const threadPath = (hubId: string, threadId: string) => `${hubPath(hubId)}?${OPEN_PARAM}=${e(threadId)}`;

/** The meeting's notes; with a moment, its transcript at that second. */
export function meetingPath(sessionId: string, startMs: number | null = null) {
  const base = `/app/notes/${e(sessionId)}`;
  return startMs === null ? base : `${base}?t=${Math.floor(startMs / 1000)}`;
}

export const boardPath = (boardId: string) => `/app/kanban?board=${e(boardId)}`;

export type HubsFilter = "active" | "all";

export const parseHubsFilter = (value: unknown): HubsFilter => (value === "all" ? "all" : "active");

export const hubsPath = (filter: HubsFilter) => (filter === "all" ? `${HUBS_PATH}?show=all` : HUBS_PATH);
