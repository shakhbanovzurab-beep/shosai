import type { AppArch, AppPlatform, AppRelease, ReleaseChannel, ReleaseMetadata } from "./contract";
import { formatBytes } from "./format";
import {
  ACCEPTED_EXTENSIONS,
  compareSemver,
  platformForFile,
  releaseMetadataSchema,
  versionProblem,
} from "./release-rules";

/* The upload form's values and the checks run on them as they change. */

export const DEFAULT_ARCH: Record<AppPlatform, AppArch> = { macos: "universal", windows: "x64" };

export type Draft = {
  platform: AppPlatform;
  channel: ReleaseChannel;
  version: string;
  arch: AppArch;
  minOs: string;
  notes: string;
  mandatory: boolean;
};

export type FieldName = "file" | "version" | "arch" | "min_os_version" | "release_notes";
export type FieldErrors = Partial<Record<FieldName, string>>;

export const initialDraft = (platform: AppPlatform): Draft => ({
  platform,
  channel: "stable",
  version: "",
  arch: DEFAULT_ARCH[platform],
  minOs: "",
  notes: "",
  mandatory: false,
});

export const toMetadata = (draft: Draft): Omit<ReleaseMetadata, "sha256"> => ({
  platform: draft.platform,
  channel: draft.channel,
  version: draft.version.trim(),
  arch: draft.arch,
  min_os_version: draft.minOs.trim(),
  release_notes: draft.notes,
  mandatory: draft.mandatory,
});

/** The parts of a chosen build file the checks look at (a browser `File` has both). */
type BuildFile = { name: string; size: number };

/** Why a chosen file can't be used, or null. */
export function fileProblem(file: BuildFile, maxBytes: number) {
  if (platformForFile(file.name) === null)
    return `Неподдерживаемый формат. Подходят ${ACCEPTED_EXTENSIONS.join(", ")}.`;
  if (file.size === 0) return "Файл пустой.";
  if (file.size > maxBytes) return `Файл весит ${formatBytes(file.size)} — больше лимита ${formatBytes(maxBytes)}.`;
  return null;
}

export function latestVersion(releases: readonly AppRelease[], platform: AppPlatform, channel: ReleaseChannel) {
  let latest: string | null = null;
  for (const r of releases) {
    if (r.platform !== platform || r.channel !== channel) continue;
    if (latest === null || compareSemver(r.version, latest) > 0) latest = r.version;
  }
  return latest;
}

/** Every problem with the current values, keyed by field. */
export function draftErrors(
  draft: Draft,
  releases: readonly AppRelease[],
  file: BuildFile | null,
  fileError: string | null,
) {
  const errors: FieldErrors = {};
  const metadata = toMetadata(draft);
  const parsed = releaseMetadataSchema.safeParse({ ...metadata, sha256: null });
  if (!parsed.success)
    for (const issue of parsed.error.issues) {
      const key = issue.path[0] as FieldName;
      errors[key] ??= issue.message;
    }
  if (!errors.version) errors.version = versionProblem(releases, metadata) ?? undefined;
  if (!file) errors.file = fileError ?? "Выберите файл сборки.";
  return errors;
}
