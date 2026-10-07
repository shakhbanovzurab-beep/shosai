import type { AppArch, AppPlatform, AppRelease, LatestRelease, ReleaseChannel } from "../domain/contract";
import { compareSemver } from "../domain/release-rules";
import { createHash } from "node:crypto";

/** Maps an install id to a stable bucket 0–99. */
const bucketOf = (installId: string) => createHash("sha256").update(installId).digest().readUInt32BE(0) % 100;

/** The newest published version for a platform and channel; see LatestRelease for the rollout rules. */
export function latestFrom(
  releases: readonly AppRelease[],
  platform: AppPlatform,
  channel: ReleaseChannel,
  arch: AppArch | null,
  installId: string | null,
): LatestRelease | null {
  const published = releases.filter(
    (r) => r.platform === platform && r.channel === channel && r.status === "published" && (!arch || r.arch === arch),
  );
  if (published.length === 0) return null;

  // One rollout per version: the lowest among its files.
  const versions = new Map<string, AppRelease[]>();
  for (const release of published) versions.set(release.version, [...(versions.get(release.version) ?? []), release]);
  const ordered = [...versions.entries()]
    .map(([version, files]) => ({ version, files, rollout: Math.min(...files.map((f) => f.rollout_percent)) }))
    .toSorted((a, b) => compareSemver(b.version, a.version));

  const bucket = installId ? bucketOf(installId) : null;
  const pick =
    (bucket === null ? ordered.find((v) => v.rollout === 100) : ordered.find((v) => bucket < v.rollout)) ??
    (bucket === null ? ordered[0] : undefined);
  if (!pick) return null;

  const head = pick.files[0];
  return {
    platform,
    channel,
    version: pick.version,
    min_os_version: head.min_os_version,
    release_notes: head.release_notes,
    mandatory: pick.files.some((f) => f.mandatory),
    rollout_percent: pick.rollout,
    published_at: head.published_at ?? head.uploaded_at,
    files: pick.files.map((f) => ({
      arch: f.arch,
      file_name: f.file_name,
      size_bytes: f.size_bytes,
      sha256: f.sha256,
      url: f.download_url,
    })),
  };
}
