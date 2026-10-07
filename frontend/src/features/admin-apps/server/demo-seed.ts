import type { AppArch, AppPlatform, AppRelease, ReleaseChannel } from "../domain/contract";
import { createHash } from "node:crypto";

/* Seed data for the demo store: metadata only, no files behind them. */

export const DEMO_UPLOADER = "Администратор";

export type Stored = { release: AppRelease; hasFile: boolean };

const day = 24 * 60 * 60 * 1000;
const ago = (days: number) => new Date(Date.now() - days * day).toISOString();
const fakeSha = (seed: string) => createHash("sha256").update(seed).digest("hex");

function seed(
  platform: AppPlatform,
  channel: ReleaseChannel,
  version: string,
  arch: AppArch,
  fileName: string,
  sizeMb: number,
  status: AppRelease["status"],
  uploadedDaysAgo: number,
  extra: Partial<AppRelease> = {},
): Stored {
  const id = `demo-${platform}-${arch}-${version}`;
  const published = status === "draft" ? null : ago(uploadedDaysAgo - 1);
  return {
    hasFile: false,
    release: {
      id,
      platform,
      channel,
      version,
      arch,
      file_name: fileName,
      size_bytes: Math.round(sizeMb * 1024 * 1024),
      sha256: fakeSha(id),
      min_os_version: platform === "macos" ? "13.0" : "10.0.19045",
      release_notes: `## Leo ${version}\n\n- Улучшена стабильность\n- Исправлены ошибки`,
      mandatory: false,
      status,
      rollout_percent: 100,
      downloads: 0,
      uploaded_by: DEMO_UPLOADER,
      uploaded_at: ago(uploadedDaysAgo),
      published_at: published,
      revoked_at: status === "revoked" ? ago(uploadedDaysAgo - 2) : null,
      download_url: `/api/admin/apps/releases/${id}/download`,
      ...extra,
    },
  };
}

export function seedReleases(): Map<string, Stored> {
  const items = [
    seed("macos", "stable", "2.3.0", "universal", "Leo-2.3.0-universal.dmg", 182.4, "published", 40, {
      downloads: 4812,
    }),
    seed("macos", "stable", "2.3.1", "universal", "Leo-2.3.1-universal.dmg", 183.1, "revoked", 30, { downloads: 214 }),
    seed("macos", "stable", "2.4.0", "universal", "Leo-2.4.0-universal.dmg", 186.7, "published", 12, {
      downloads: 1630,
      rollout_percent: 50,
    }),
    seed("macos", "beta", "2.5.0-beta.1", "apple_silicon", "Leo-2.5.0-beta.1-arm64.dmg", 104.2, "published", 5, {
      downloads: 96,
    }),
    seed("macos", "beta", "2.5.0-beta.2", "apple_silicon", "Leo-2.5.0-beta.2-arm64.dmg", 104.9, "draft", 1),
    seed("windows", "stable", "2.3.0", "x64", "Leo-Setup-2.3.0-x64.exe", 141.3, "published", 40, { downloads: 9204 }),
    seed("windows", "stable", "2.4.0", "x64", "Leo-Setup-2.4.0-x64.exe", 143.8, "published", 12, { downloads: 3175 }),
    seed("windows", "stable", "2.4.0", "arm64", "Leo-Setup-2.4.0-arm64.exe", 139.2, "published", 12, {
      downloads: 288,
    }),
    seed("windows", "beta", "2.5.0-beta.1", "x64", "Leo-2.5.0-beta.1-x64.msix", 128.6, "draft", 2),
  ];
  return new Map(items.map((item) => [item.release.id, item]));
}
