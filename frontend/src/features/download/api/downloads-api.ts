import { ApiError } from "@/lib/api/errors";
import { apiRequest } from "@/lib/api/request";

import {
  DESKTOP_PLATFORMS,
  type DesktopDownloads,
  type DesktopPlatform,
  type DesktopRelease,
} from "../domain/contract";

// Ответ публичного GET /apps/latest: в релизе больше полей, странице нужны эти.
type LatestRelease = DesktopRelease & { files: (DesktopRelease["files"][number] & Record<string, unknown>)[] };

const toRelease = (latest: LatestRelease): DesktopRelease => ({
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
 * Самая новая опубликованная стабильная сборка платформы, без install id (чтобы версия на поэтапной раскатке
 * не предлагалась новым загрузкам); `null`, если сборок нет, "error", если её не удалось прочитать.
 */
async function latestFor(platform: DesktopPlatform): Promise<DesktopRelease | null | "error"> {
  try {
    return toRelease(await apiRequest<LatestRelease>(`/api/apps/latest?platform=${platform}&channel=stable`));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    return "error";
  }
}

/** Обе платформы читаются параллельно; сбой одной не скрывает другую. */
export async function fetchDesktopDownloads(): Promise<DesktopDownloads> {
  const [macos, windows] = await Promise.all(DESKTOP_PLATFORMS.map(latestFor));
  return { macos, windows };
}
