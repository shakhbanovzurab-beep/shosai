/**
 * Knowledge API contract (what Leo answers from in Personal), shared by the UI and the route
 * handlers in `server/` (mounted under `src/app/api/knowledge-base`). The handlers proxy to the FastAPI service at
 * `BACKEND_API_URL` (paths below, under `/v1/knowledge-base`) and fall back to an
 * in-memory demo when it is unset. Field names are snake_case to match Pydantic models;
 * errors are FastAPI's `{ "detail": string }`.
 */

/* ---------- Leo's index: GET /index ---------- */

/**
 * The files Leo uses live in File Manager (see docs/file-manager-api.md): a file or a folder marked
 * "Use with Leo" is indexed, and its status is on the file. This endpoint describes the index itself.
 */
export type IndexSettings = {
  embedding_model: string;
  dimensions: number;
  chunk_size: number;
  chunk_overlap: number;
};

/** `limit_bytes`: how much of the account's files Leo may use on its plan; null for no limit. */
export type IndexResponse = { index: IndexSettings; limit_bytes: number | null };

/* ---------- Connectors: GET /connectors, PUT/DELETE /connectors/{id}, POST /connectors/{id}/sync ---------- */

export const CONNECTOR_IDS = [
  "slack",
  "confluence",
  "notion",
  "obsidian",
  "jira",
  "github",
  "gitlab",
  "google_drive",
  "sharepoint",
  "dropbox",
  "yandex_disk",
  "website",
] as const;

export type ConnectorId = (typeof CONNECTOR_IDS)[number];

export type ConnectorStatus = "disconnected" | "connecting" | "syncing" | "connected" | "error";

export type Connector = {
  id: ConnectorId;
  status: ConnectorStatus;
  /** Scoping settings as saved (channels, folders…). OAuth tokens stay on the backend. Empty while disconnected. */
  config: Record<string, string>;
  items_indexed: number;
  last_synced_at: string | null;
  error: string | null;
};

export type ConnectorsResponse = { connectors: Connector[] };

/** PUT /connectors/{id} body. */
export type ConnectRequest = { config: Record<string, string> };

/**
 * OAuth 2.0 sources: the backend saves the settings, sets status "connecting" and returns the
 * provider's `authorize_url`; its callback stores the tokens, starts the first sync and redirects
 * to `/app/knowledge-base?tab=sources`. Public sources return `authorize_url: null`.
 */
export type ConnectResponse = { connector: Connector; authorize_url: string | null };

export const BUSY_CONNECTOR: ReadonlySet<ConnectorStatus> = new Set(["connecting", "syncing"]);
