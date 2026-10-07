import { z } from "zod";

import {
  APP_PLATFORMS,
  type AppPlatform,
  type AppRelease,
  ARCHS_BY_PLATFORM,
  EXTENSIONS_BY_PLATFORM,
  RELEASE_CHANNELS,
  RELEASE_NOTES_MAX,
  type ReleaseChannel,
  type ReleaseMetadata,
} from "./contract";

/* Rules shared by the upload form and the demo route handlers, so both say the same thing. */

const SEMVER =
  /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?$/;
const OS_VERSION = /^\d+(?:\.\d+){0,3}$/;
const SHA256_HEX = /^[0-9a-f]{64}$/;
const NUMERIC = /^\d+$/;

/** Orders two valid semantic versions: negative if a < b, 0 if equal (build metadata ignored), positive if a > b. */
export function compareSemver(a: string, b: string): number {
  const [, aMaj, aMin, aPat, aPre] = SEMVER.exec(a) ?? [];
  const [, bMaj, bMin, bPat, bPre] = SEMVER.exec(b) ?? [];
  const core = [Number(aMaj) - Number(bMaj), Number(aMin) - Number(bMin), Number(aPat) - Number(bPat)];
  const diff = core.find((d) => d !== 0);
  if (diff !== undefined) return diff;
  if (aPre === bPre) return 0;
  // A release outranks its pre-releases: 2.0.0 > 2.0.0-beta.1.
  if (aPre === undefined) return 1;
  if (bPre === undefined) return -1;
  const aIds = aPre.split(".");
  const bIds = bPre.split(".");
  for (let i = 0; i < Math.max(aIds.length, bIds.length); i++) {
    const x = aIds[i];
    const y = bIds[i];
    if (x === undefined) return -1;
    if (y === undefined) return 1;
    if (x === y) continue;
    const xNum = NUMERIC.test(x);
    const yNum = NUMERIC.test(y);
    if (xNum && yNum) return Number(x) - Number(y);
    if (xNum !== yNum) return xNum ? -1 : 1;
    return x < y ? -1 : 1;
  }
  return 0;
}

export function fileExtension(fileName: string) {
  const dot = fileName.lastIndexOf(".");
  return dot === -1 ? "" : fileName.slice(dot).toLowerCase();
}

/** macOS for .dmg/.pkg/.zip, Windows for .exe/.msi/.msix, null for anything else. */
export function platformForFile(fileName: string): AppPlatform | null {
  const ext = fileExtension(fileName);
  return APP_PLATFORMS.find((platform) => EXTENSIONS_BY_PLATFORM[platform].includes(ext)) ?? null;
}

export const ACCEPTED_EXTENSIONS = APP_PLATFORMS.flatMap((platform) => EXTENSIONS_BY_PLATFORM[platform]);

export const releaseMetadataSchema = z
  .object({
    platform: z.enum(APP_PLATFORMS),
    channel: z.enum(RELEASE_CHANNELS),
    version: z.string().trim().regex(SEMVER, "Укажите версию в формате SemVer, например 2.4.0 или 2.5.0-beta.1."),
    arch: z.string(),
    min_os_version: z.string().trim().regex(OS_VERSION, "Укажите минимальную версию ОС цифрами, например 13.0."),
    release_notes: z.string().max(RELEASE_NOTES_MAX, "Описание изменений слишком длинное."),
    mandatory: z.boolean(),
    sha256: z.string().regex(SHA256_HEX).nullable(),
  })
  .refine((meta) => (ARCHS_BY_PLATFORM[meta.platform] as readonly string[]).includes(meta.arch), {
    message: "Эта архитектура недоступна для выбранной платформы.",
    path: ["arch"],
  })
  .transform((meta) => meta as ReleaseMetadata);

/**
 * A new version must be greater than every version already uploaded for that platform and channel
 * (revoked ones included — a version number is never reused). The same version may be uploaded once
 * more for another architecture, e.g. an Intel build next to the Apple Silicon one.
 * Returns a Russian error message, or null when the version is fine.
 */
export function versionProblem(
  releases: readonly AppRelease[],
  meta: Pick<ReleaseMetadata, "platform" | "channel" | "version" | "arch">,
) {
  let latest: AppRelease | null = null;
  for (const release of releases) {
    if (release.platform !== meta.platform || release.channel !== meta.channel) continue;
    if (latest === null || compareSemver(release.version, latest.version) > 0) latest = release;
  }
  if (latest === null) return null;
  const order = compareSemver(meta.version, latest.version);
  if (order > 0) return null;
  if (order === 0) {
    const taken = releases.some(
      (r) =>
        r.platform === meta.platform &&
        r.channel === meta.channel &&
        r.arch === meta.arch &&
        compareSemver(r.version, meta.version) === 0,
    );
    return taken ? `Сборка ${meta.version} для этой архитектуры уже загружена.` : null;
  }
  return `Версия должна быть больше ${latest.version} — последней в этом канале.`;
}

/** The newest published version in a channel, with its file for each architecture. */
export function currentVersion(releases: readonly AppRelease[], platform: AppPlatform, channel: ReleaseChannel) {
  let files: AppRelease[] = [];
  for (const release of releases) {
    if (release.platform !== platform || release.channel !== channel || release.status !== "published") continue;
    const order = files.length === 0 ? 1 : compareSemver(release.version, files[0].version);
    if (order > 0) files = [release];
    else if (order === 0) files.push(release);
  }
  return files;
}
