/**
 * Settings API contract, shared by the settings dialog and the route handlers in
 * `src/features/settings/server` (served under `/api/settings`). They proxy to
 * `${BACKEND_API_URL}/v1/settings/*` when it is set and fall back to an in-memory demo otherwise.
 * snake_case to match Pydantic; errors are FastAPI's `{ "detail": string }`. See docs/settings-api.md.
 * Billing and usage, MCP, your data, memory and connectors have their own contract files beside this one.
 */

import type { HotkeyBindings } from "./hotkeys";

/* ---------- Preferences: GET /settings, PATCH /settings (any subset) ---------- */

/** How much Leo says by default, in the order the picker shows them. */
export const RESPONSE_LENGTHS = ["concise", "balanced", "detailed"] as const;
export type ResponseLength = (typeof RESPONSE_LENGTHS)[number];

export type UserSettings = {
  /* Account */
  full_name: string;
  /** What Leo calls the user. */
  display_name: string;
  /** Read-only here; changed through the identity provider. */
  email: string;
  /** Set with PUT /settings/avatar, cleared with DELETE; null shows initials. */
  avatar_url: string | null;
  /** One of WORK_ROLES; helps Leo pitch answers to the user's field. */
  work_role: WorkRole;
  /* Privacy */
  improve_models: boolean;
  share_location: boolean;
  /* Leo */
  /** "auto" lets Leo pick per task; otherwise a text model id from GET /studio/models (the subscription's list). */
  leo_model: string;
  /** A language code from src/lib/language.ts, or "auto" to answer in the interface language. */
  response_language: string;
  response_length: ResponseLength;
  /* Leo › Advanced: what Leo may use; anything off is neither offered nor used */
  web_search: boolean;
  /** Off also removes the microphone from the interface. */
  voice_mode: boolean;
  knowledge_base_search: boolean;
  /** Search sources connected in Knowledge › Sources (Google Drive, Notion…). */
  connected_services_search: boolean;
  /* Memory */
  memory_enabled: boolean;
  /* Hotkeys */
  /**
   * The desktop app's global shortcuts the user changed (see domain/hotkeys.ts): a combo such as
   * "Mod+Alt+Z", or null for "off". A PATCH replaces the whole map; an id left out uses its default.
   */
  hotkeys: HotkeyBindings;
};

export type SettingsPatch = Partial<Omit<UserSettings, "email" | "avatar_url">>;

/* ---------- Account deletion: POST /settings/account/delete ---------- */

/** The user retypes their email to confirm; the backend checks it matches before deleting anything. */
export type DeleteAccountRequest = { confirm_email: string };
/** Deletion starts at once; afterwards the session is signed out. */
export type DeleteAccountResponse = { deleted: true };

/* ---------- Avatar: PUT /settings/avatar (multipart, field "file"), DELETE /settings/avatar ---------- */

/** The browser crops to a square and scales to this many pixels a side before uploading. */
export const AVATAR_SIZE = 256;
/** Largest upload the server accepts, after the browser has scaled it. */
export const AVATAR_MAX_BYTES = 1024 * 1024;
export const AVATAR_TYPES = ["image/webp", "image/jpeg", "image/png"] as const;

export const NAME_MAX = 80;

/** "What best describes your work?" — codes in the order the menu shows them, "other" last; the UI words them. */
export const WORK_ROLES = [
  "product_management",
  "engineering",
  "human_resources",
  "finance",
  "marketing",
  "sales",
  "operations",
  "data_science",
  "design",
  "legal",
  "scientist",
  "student",
  "founder",
  "healthcare",
  "writer",
  "educator",
  "consultant",
  "researcher",
  "software_engineer",
  "other",
] as const;

export type WorkRole = (typeof WORK_ROLES)[number];

export const isWorkRole = (value: string): value is WorkRole => (WORK_ROLES as readonly string[]).includes(value);
