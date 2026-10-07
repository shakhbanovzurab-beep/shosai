/*
 * ---------- Connectors (OAuth 2.0) ----------
 * GET /settings/connectors, PATCH /settings/connectors/{id}
 *
 * Connecting is the OAuth 2.0 authorization code flow with PKCE, run by the backend:
 * 1. PATCH { connected: true } → the backend creates `state` and a PKCE verifier and returns the
 *    provider's consent URL as `authorize_url` (the connector stays disconnected for now).
 * 2. The app opens that URL in a popup; the user approves or denies on the provider's page.
 * 3. The provider redirects to the backend's callback with `code` and `state`; the backend checks
 *    `state`, exchanges the code for tokens, stores them, and redirects the popup to
 *    `{APP_URL}/oauth/callback?connector={id}&status=connected` (or `status=error&error=<message>`,
 *    `status=denied`).
 * 4. That page posts an `OAuthResultMessage` to the app and closes; the app reloads the connectors.
 * PATCH { connected: false } revokes the tokens with the provider and forgets them.
 */

export const CONNECTOR_CATEGORIES = ["mail", "files", "notes", "communication", "tasks", "crm"] as const;
export type ConnectorCategory = (typeof CONNECTOR_CATEGORIES)[number];

/** An app Leo can read from and act in once the user connects their account. */
export type Connector = {
  id: string;
  name: string;
  category: ConnectorCategory;
  connected: boolean;
  /** The connected account, e.g. an email address; null while disconnected or unknown. */
  account: string | null;
};

export type ConnectorsResponse = { connectors: Connector[] };

export type ConnectorUpdate = { connected: boolean };

/** `authorize_url` is set when connecting needs the provider's consent screen (always, for OAuth). */
export type ConnectorUpdateResponse = { connector: Connector; authorize_url: string | null };

export type OAuthStatus = "connected" | "denied" | "error";

/** Posted by `/oauth/callback` to the window that opened the consent popup. */
export type OAuthResultMessage = {
  type: typeof OAUTH_MESSAGE_TYPE;
  connector: string;
  status: OAuthStatus;
  error: string | null;
};

export const OAUTH_MESSAGE_TYPE = "leo:connector-oauth";
