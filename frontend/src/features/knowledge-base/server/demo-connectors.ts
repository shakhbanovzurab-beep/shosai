import { connectorById } from "../domain/connectors";
import { CONNECTOR_IDS, type Connector, type ConnectorId } from "../domain/contract";
import type { Problem } from "./problems";

/*
 * In-memory stand-in for connector syncing, used when BACKEND_API_URL is unset. It skips
 * the OAuth hand-off and connects straight away; a connect or sync runs for a few seconds and then
 * reports a plausible item count.
 */

const SYNC_MS = 5000;

type StoredConnector = { config: Record<string, string>; syncStartedAt: number | null; items: number };

// On globalThis so every route handler bundle shares one store within the server process.
const shared = globalThis as typeof globalThis & { kbDemoConnectors?: Map<ConnectorId, StoredConnector> };
shared.kbDemoConnectors ??= new Map<ConnectorId, StoredConnector>();
const store = shared.kbDemoConnectors;

const isConnectorId = (id: string): id is ConnectorId => (CONNECTOR_IDS as readonly string[]).includes(id);

function present(id: ConnectorId, now: number): Connector {
  const saved = store.get(id);
  if (!saved) return { id, status: "disconnected", config: {}, items_indexed: 0, last_synced_at: null, error: null };
  const syncing = saved.syncStartedAt !== null && now - saved.syncStartedAt < SYNC_MS;
  const lastSync = saved.syncStartedAt === null ? null : new Date(saved.syncStartedAt + SYNC_MS).toISOString();
  return {
    id,
    status: syncing ? "syncing" : "connected",
    config: saved.config,
    items_indexed: syncing ? 0 : saved.items,
    last_synced_at: syncing ? null : lastSync,
    error: null,
  };
}

export function listConnectors(): Connector[] {
  const now = Date.now();
  return CONNECTOR_IDS.map((id) => present(id, now));
}

/** Saves settings and starts the first sync. `null` for an unknown id. */
export function connect(id: string, config: Record<string, string>): Connector | Problem | null {
  if (!isConnectorId(id)) return null;
  const definition = connectorById(id);
  const missing = definition?.fields.find((f) => f.required && !config[f.key]?.trim());
  if (missing) return { code: "fieldRequired", field: missing.key };
  const saved = Object.fromEntries(
    (definition?.fields ?? []).filter((f) => config[f.key]?.trim()).map((f) => [f.key, config[f.key].trim()]),
  );
  store.set(id, { config: saved, syncStartedAt: Date.now(), items: 40 + Math.floor(Math.random() * 900) });
  return present(id, Date.now());
}

export function disconnect(id: string): boolean {
  return isConnectorId(id) && store.delete(id);
}

export function syncNow(id: string): Connector | null {
  if (!isConnectorId(id)) return null;
  const saved = store.get(id);
  if (!saved) return null;
  saved.syncStartedAt = Date.now();
  saved.items += Math.floor(Math.random() * 25);
  return present(id, Date.now());
}
