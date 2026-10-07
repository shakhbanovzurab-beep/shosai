import type { Connector, OAuthStatus } from "../domain/connectors-contract";
import type { Problem } from "./problems";

/*
 * In-memory connectors for the demo. Connecting walks the same OAuth 2.0 steps as the real backend,
 * but the "provider" is our own demo consent page, so no real account is ever touched.
 */

const DEMO_ACCOUNT = "arham@lumen.so";

const INITIAL: Connector[] = [
  { id: "gmail", name: "Gmail", category: "mail", connected: true, account: DEMO_ACCOUNT },
  { id: "outlook", name: "Outlook", category: "mail", connected: false, account: null },
  { id: "google_drive", name: "Google Drive", category: "files", connected: true, account: DEMO_ACCOUNT },
  { id: "dropbox", name: "Dropbox", category: "files", connected: true, account: DEMO_ACCOUNT },
  { id: "yandex_disk", name: "Yandex Disk", category: "files", connected: false, account: null },
  { id: "notion", name: "Notion", category: "notes", connected: false, account: null },
  { id: "confluence", name: "Confluence", category: "notes", connected: false, account: null },
  { id: "slack", name: "Slack", category: "communication", connected: false, account: null },
  { id: "github", name: "GitHub", category: "tasks", connected: false, account: null },
  { id: "gitlab", name: "GitLab", category: "tasks", connected: false, account: null },
  { id: "jira", name: "Jira", category: "tasks", connected: false, account: null },
  { id: "hubspot", name: "HubSpot", category: "crm", connected: false, account: null },
];

/** Pending authorizations expire like real OAuth `state` values do. */
const STATE_TTL_MS = 10 * 60 * 1000;

const shared = globalThis as typeof globalThis & {
  settingsDemoConnectors?: Map<string, Connector>;
  settingsDemoOAuthStates?: Map<string, { connectorId: string; expiresAt: number }>;
};
shared.settingsDemoConnectors ??= new Map(INITIAL.map((connector) => [connector.id, connector]));
shared.settingsDemoOAuthStates ??= new Map();
const store = shared.settingsDemoConnectors;
const states = shared.settingsDemoOAuthStates;

export const listConnectors = () => [...store.values()];
export const getConnector = (id: string) => store.get(id) ?? null;

/** Step 1: remembers a one-time `state` and returns the consent URL to open in the popup. */
export function beginAuthorization(id: string): string | null {
  if (!store.has(id)) return null;
  const state = crypto.randomUUID();
  states.set(state, { connectorId: id, expiresAt: Date.now() + STATE_TTL_MS });
  const params = new URLSearchParams({ connector: id, state });
  return `/oauth/demo-authorize?${params}`;
}

/** Step 3: checks the one-time `state`; on approval stores the connection. A failure is a problem code. */
export function completeAuthorization(
  id: string,
  state: string,
  approved: boolean,
): { status: OAuthStatus; error: Extract<Problem, "authorizationExpired" | "connectorNotFound"> | null } {
  const pending = states.get(state);
  states.delete(state);
  if (!pending || pending.connectorId !== id || pending.expiresAt < Date.now()) {
    return { status: "error", error: "authorizationExpired" };
  }
  if (!approved) return { status: "denied", error: null };
  const connector = store.get(id);
  if (!connector) return { status: "error", error: "connectorNotFound" };
  store.set(id, { ...connector, connected: true, account: DEMO_ACCOUNT });
  return { status: "connected", error: null };
}

export function disconnect(id: string): Connector | null {
  const connector = store.get(id);
  if (!connector) return null;
  const next: Connector = { ...connector, connected: false, account: null };
  store.set(id, next);
  return next;
}
