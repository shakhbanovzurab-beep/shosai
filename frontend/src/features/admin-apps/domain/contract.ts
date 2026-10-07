/**
 * Desktop app releases contract, shared by Admin › Приложения, the route handlers in
 * `server/releases-route.ts` (mounted under `src/app/api/admin/apps`) and the public endpoint in
 * `server/latest-route.ts` (mounted at `src/app/api/apps/latest`). The routes proxy to
 * `${BACKEND_API_URL}/v1/admin/apps/*` (and `/v1/apps/latest`) when it is set and fall back to an
 * in-memory demo otherwise. snake_case to match Pydantic; errors are FastAPI's `{ "detail": string }`.
 *
 * Admin endpoints:
 * - GET    /admin/apps/releases                → ReleasesResponse
 * - POST   /admin/apps/releases                → AppRelease (201). multipart/form-data, `metadata` part
 *          (JSON ReleaseMetadata) first, then the build in the `file` part. Always created as a draft.
 * - PATCH  /admin/apps/releases/{id}           → AppRelease. Body ReleasePatch.
 * - DELETE /admin/apps/releases/{id}           → 204. Drafts only (409 otherwise).
 * - GET    /admin/apps/releases/{id}/download  → the build as application/octet-stream.
 *
 * Public endpoint (no auth; for the download page and the apps' auto-updaters):
 * - GET /apps/latest?platform=macos|windows&channel=stable|beta[&arch=…][&install_id=…] → LatestRelease, 404 if none.
 */

export const APP_PLATFORMS = ["macos", "windows"] as const;
export type AppPlatform = (typeof APP_PLATFORMS)[number];

export const RELEASE_CHANNELS = ["stable", "beta"] as const;
export type ReleaseChannel = (typeof RELEASE_CHANNELS)[number];

export const RELEASE_STATUSES = ["draft", "published", "revoked"] as const;
export type ReleaseStatus = (typeof RELEASE_STATUSES)[number];

export const MACOS_ARCHS = ["apple_silicon", "intel", "universal"] as const;
export const WINDOWS_ARCHS = ["x64", "arm64"] as const;
export type MacosArch = (typeof MACOS_ARCHS)[number];
export type WindowsArch = (typeof WINDOWS_ARCHS)[number];
export type AppArch = MacosArch | WindowsArch;

export const ARCHS_BY_PLATFORM: Record<AppPlatform, readonly AppArch[]> = {
  macos: MACOS_ARCHS,
  windows: WINDOWS_ARCHS,
};

/** File extensions accepted per platform, lower case with the dot. */
export const EXTENSIONS_BY_PLATFORM: Record<AppPlatform, readonly string[]> = {
  macos: [".dmg", ".pkg", ".zip"],
  windows: [".exe", ".msi", ".msix"],
};

/** Largest build the server accepts. */
export const RELEASE_MAX_BYTES = 500 * 1024 * 1024;
export const RELEASE_NOTES_MAX = 20_000;

export type AppRelease = {
  id: string;
  platform: AppPlatform;
  channel: ReleaseChannel;
  /** Semantic version, e.g. "2.4.0" or "2.5.0-beta.1". Unique per platform, channel and arch, never reused. */
  version: string;
  arch: AppArch;
  file_name: string;
  size_bytes: number;
  /** Hex SHA-256 of the file, computed by the server while receiving it (and checked against the browser's). */
  sha256: string;
  /** e.g. "13.0" for macOS, "10.0.19045" for Windows. */
  min_os_version: string;
  /** Markdown. */
  release_notes: string;
  /** The updater installs it without asking. */
  mandatory: boolean;
  /** draft → published → revoked; a draft can be deleted, the others can't. */
  status: ReleaseStatus;
  /**
   * Share of installs (0–100) offered this build by the updater. Only adjustable for published stable
   * builds; always 100 otherwise.
   */
  rollout_percent: number;
  downloads: number;
  uploaded_by: string;
  uploaded_at: string;
  published_at: string | null;
  revoked_at: string | null;
  /** Where the admin downloads the file. */
  download_url: string;
};

export type ReleasesResponse = {
  /** Newest upload first. */
  releases: AppRelease[];
  max_upload_bytes: number;
};

/** The `metadata` part of POST /admin/apps/releases. */
export type ReleaseMetadata = {
  platform: AppPlatform;
  channel: ReleaseChannel;
  version: string;
  arch: AppArch;
  min_os_version: string;
  release_notes: string;
  mandatory: boolean;
  /** SHA-256 the browser computed, or null when it couldn't (plain http). The server rejects a mismatch. */
  sha256: string | null;
};

/** PATCH /admin/apps/releases/{id}. Publish a draft, revoke a published build, or change a stable build's rollout. */
export type ReleasePatch = {
  status?: Exclude<ReleaseStatus, "draft">;
  rollout_percent?: number;
};

/* ---------- Public: GET /apps/latest ---------- */

export type LatestReleaseFile = {
  arch: AppArch;
  file_name: string;
  size_bytes: number;
  sha256: string;
  url: string;
};

/**
 * The newest published version for a platform and channel, with one file per architecture.
 * With `install_id` (a stable random id per installation) the server picks the newest version whose
 * rollout covers that install's bucket (0–99). Without it, the newest fully rolled out version is
 * returned, falling back to the newest published one.
 */
export type LatestRelease = {
  platform: AppPlatform;
  channel: ReleaseChannel;
  version: string;
  min_os_version: string;
  release_notes: string;
  mandatory: boolean;
  rollout_percent: number;
  published_at: string;
  files: LatestReleaseFile[];
};
