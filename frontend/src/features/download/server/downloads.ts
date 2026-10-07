import { latestPublishedRelease, type PublicAppRelease } from "@/features/admin-apps/server";
import { fetchFromBackend } from "@/server/backend-proxy";

import {
  DESKTOP_PLATFORMS,
  type DesktopDownloads,
  type DesktopPlatform,
  type DesktopRelease,
} from "../domain/contract";

const toRelease = (latest: PublicAppRelease): DesktopRelease => ({
  platform: latest.platform,
  version: latest.version,
  min_os_version: latest.min_os_version,
  published_at: latest.published_at,
  files: latest.files.map(({ arch, file_name, size_bytes, sha256, url }) => ({
    arch,
    file_name,
    size_bytes,
    sha256,
    url,
  })),
});

/**
 * The newest published stable build for one platform, the same answer as the public GET /apps/latest
 * without an install id (so a version still rolling out isn't offered to new downloads).
 */
async function latestFor(platform: DesktopPlatform): Promise<DesktopRelease | null | "error"> {
  try {
    const upstream = fetchFromBackend(`/v1/apps/latest?platform=${platform}&channel=stable`);
    if (!upstream) {
      const demo = latestPublishedRelease(platform, "stable", null, null);
      return demo ? toRelease(demo) : null;
    }
    const response = await upstream;
    if (response.status === 404) return null;
    if (!response.ok) return "error";
    return toRelease((await response.json()) as PublicAppRelease);
  } catch {
    return "error";
  }
}

/** Both platforms, read in parallel; one failing doesn't hide the other. */
export async function getDesktopDownloads(): Promise<DesktopDownloads> {
  const [macos, windows] = await Promise.all(DESKTOP_PLATFORMS.map(latestFor));
  return { macos, windows };
}
