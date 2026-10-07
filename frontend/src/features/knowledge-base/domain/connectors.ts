import type { ConnectorId } from "./contract";

/*
 * Every source Leo can sync from. Labels, help and descriptions are worded in the UI by connector id and
 * field key (the `knowledgeBaseSources` catalog). What stays here is written the same in every language:
 * brand names, and examples that are identifiers, paths, URLs or query syntax ("#general", "ENG", JQL).
 */

/** The settings a source can be narrowed to; each key has a label (and maybe help) in the catalog. */
export type ConnectorFieldKey =
  | "channels"
  | "spaces"
  | "repository"
  | "branch"
  | "jql"
  | "repositories"
  | "base_url"
  | "projects"
  | "folder_id"
  | "site_url"
  | "path"
  | "start_url"
  | "max_depth"
  | "include";

const HELP_KEYS = [
  "channels",
  "spaces",
  "repositories",
  "base_url",
  "projects",
  "folder_id",
  "site_url",
  "max_depth",
] as const satisfies ConnectorFieldKey[];

/** A field whose key also has a help line in the catalog. */
export type HelpFieldKey = (typeof HELP_KEYS)[number];
export const hasHelp = (key: ConnectorFieldKey): key is HelpFieldKey => (HELP_KEYS as readonly string[]).includes(key);

/** Optional scoping for a source; sign-in itself happens at the provider. */
export type ConnectorField = {
  key: ConnectorFieldKey;
  type: "text" | "url" | "number" | "textarea";
  /** A sample value shown as the placeholder, written as the user would type it. */
  example?: string;
  required?: boolean;
};

export type ConnectorDefinition = {
  id: ConnectorId;
  /** The brand name, the same in every language; null for a generic source the catalog names ("Website"). */
  brand: string | null;
  /**
   * "oauth": OAuth 2.0 — the backend returns `authorize_url`, the user approves read-only access at
   * `provider`, and the backend's callback finishes the connection. "public": no sign-in.
   */
  auth: "oauth" | "public";
  /** Who the user signs in with, when it isn't the source itself (e.g. Atlassian for Jira). */
  provider?: string;
  fields: ConnectorField[];
};

export const CONNECTORS: ConnectorDefinition[] = [
  {
    id: "slack",
    brand: "Slack",
    auth: "oauth",
    fields: [{ key: "channels", type: "text", example: "#general, #support" }],
  },
  {
    id: "confluence",
    brand: "Confluence",
    auth: "oauth",
    provider: "Atlassian",
    fields: [{ key: "spaces", type: "text", example: "ENG, OPS" }],
  },
  { id: "notion", brand: "Notion", auth: "oauth", fields: [] },
  {
    id: "obsidian",
    brand: "Obsidian",
    auth: "oauth",
    provider: "GitHub",
    fields: [
      { key: "repository", type: "text", example: "you/obsidian-vault", required: true },
      { key: "branch", type: "text", example: "main" },
    ],
  },
  {
    id: "jira",
    brand: "Jira",
    auth: "oauth",
    provider: "Atlassian",
    fields: [{ key: "jql", type: "textarea", example: "project = SUP AND updated >= -90d" }],
  },
  {
    id: "github",
    brand: "GitHub",
    auth: "oauth",
    fields: [{ key: "repositories", type: "textarea", example: "org/repo\norg/another-repo" }],
  },
  {
    id: "gitlab",
    brand: "GitLab",
    auth: "oauth",
    fields: [
      { key: "base_url", type: "url", example: "https://gitlab.com" },
      { key: "projects", type: "textarea", example: "group/project" },
    ],
  },
  {
    id: "google_drive",
    brand: "Google Drive",
    auth: "oauth",
    provider: "Google",
    fields: [{ key: "folder_id", type: "text" }],
  },
  {
    id: "sharepoint",
    brand: "SharePoint & OneDrive",
    auth: "oauth",
    provider: "Microsoft",
    fields: [{ key: "site_url", type: "url", example: "https://contoso.sharepoint.com/sites/team" }],
  },
  { id: "dropbox", brand: "Dropbox", auth: "oauth", fields: [{ key: "path", type: "text", example: "/Team/Docs" }] },
  {
    id: "yandex_disk",
    brand: "Yandex Disk",
    auth: "oauth",
    provider: "Yandex ID",
    fields: [{ key: "path", type: "text", example: "disk:/Documents" }],
  },
  {
    id: "website",
    brand: null,
    auth: "public",
    fields: [
      { key: "start_url", type: "url", example: "https://docs.example.com", required: true },
      { key: "max_depth", type: "number", example: "3" },
      { key: "include", type: "text", example: "/docs/, /guides/" },
    ],
  },
];

export const connectorById = (id: ConnectorId) => CONNECTORS.find((c) => c.id === id);
