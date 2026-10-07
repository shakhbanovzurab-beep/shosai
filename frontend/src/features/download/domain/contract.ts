/**
 * What the download page shows for each desktop platform: the newest published stable build, in the
 * shape of the public `GET /apps/latest` (see the admin-apps slice, which manages the releases).
 */

export const DESKTOP_PLATFORMS = ["macos", "windows"] as const;
export type DesktopPlatform = (typeof DESKTOP_PLATFORMS)[number];

export type DesktopBuild = {
  /** "universal", "apple_silicon" or "intel" on macOS; "x64" or "arm64" on Windows. */
  arch: string;
  file_name: string;
  size_bytes: number;
  sha256: string;
  url: string;
};

export type DesktopRelease = {
  platform: DesktopPlatform;
  version: string;
  /** e.g. "13.0" for macOS, "10.0.19045" for Windows. */
  min_os_version: string;
  published_at: string;
  files: DesktopBuild[];
};

/** Per platform: its release, `null` when nothing is published yet, or "error" when it couldn't be read. */
export type DesktopDownloads = Record<DesktopPlatform, DesktopRelease | null | "error">;
