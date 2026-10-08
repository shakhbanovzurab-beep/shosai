import {
  type AppArch,
  type AppPlatform,
  type AppRelease,
  RELEASE_MAX_BYTES,
  type ReleaseChannel,
  type ReleaseMetadata,
  type ReleasePatch,
} from "../domain/contract";
import { ACCEPTED_EXTENSIONS, fileExtension, releaseMetadataSchema, versionProblem } from "../domain/release-rules";
import { DEMO_UPLOADER, type Stored, seedReleases } from "./demo-seed";
import { latestFrom } from "./latest-release";
import { ReleaseError } from "./release-error";

/*
 * Demo store for desktop app releases in the development mocks. Metadata and uploaded files live in the
 * page's memory (lost on reload). Seeded releases have metadata only; downloading them answers 404.
 */

const shared = globalThis as typeof globalThis & { adminDemoAppReleases?: Map<string, Stored> };
shared.adminDemoAppReleases ??= seedReleases();
const store = shared.adminDemoAppReleases;
const files = new Map<string, Blob>();

export const listReleases = () =>
  [...store.values()].map((s) => s.release).toSorted((a, b) => b.uploaded_at.localeCompare(a.uploaded_at));

/** The public «latest» answer computed from the demo store. */
export const latestRelease = (
  platform: AppPlatform,
  channel: ReleaseChannel,
  arch: AppArch | null,
  installId: string | null,
) => latestFrom(listReleases(), platform, channel, arch, installId);

const hexDigest = async (file: Blob) =>
  Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", await file.arrayBuffer())), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");

// Метаданные сборки из поля формы `metadata`; ошибка — ReleaseError с кодом ответа.
function parseMetadata(value: FormDataEntryValue | null): ReleaseMetadata {
  if (typeof value !== "string") throw new ReleaseError("Отправьте поле `metadata` перед файлом.", 422);
  let json: unknown = null;
  try {
    json = JSON.parse(value);
  } catch {
    throw new ReleaseError("Поле `metadata` должно быть JSON.", 422);
  }
  const parsed = releaseMetadataSchema.safeParse(json);
  if (!parsed.success) throw new ReleaseError(parsed.error.issues[0]?.message ?? "Неверные данные сборки.", 422);
  const problem = versionProblem(listReleases(), parsed.data);
  if (problem) throw new ReleaseError(problem, 409);
  return parsed.data;
}

/** Receives POST /admin/apps/releases and stores it as a draft. Throws ReleaseError on any problem. */
export async function createRelease(request: Request): Promise<AppRelease> {
  if (!(request.headers.get("content-type") ?? "").startsWith("multipart/form-data"))
    throw new ReleaseError("Отправьте форму multipart/form-data.", 415);
  const form = await request.formData();
  const data = parseMetadata(form.get("metadata"));
  const upload = form.get("file");
  if (!(upload instanceof File)) throw new ReleaseError("Прикрепите сборку в поле `file`.", 422);
  if (upload.size > RELEASE_MAX_BYTES) throw new ReleaseError("Файл больше 500 МБ.", 413);
  // The platform may be overridden (e.g. a portable .zip for Windows), so any accepted type will do.
  if (!ACCEPTED_EXTENSIONS.includes(fileExtension(upload.name)))
    throw new ReleaseError(`Подходят файлы ${ACCEPTED_EXTENSIONS.join(", ")}.`, 422);
  if (upload.size === 0) throw new ReleaseError("Файл пустой.", 422);
  const sha256 = await hexDigest(upload);
  if (data.sha256 !== null && data.sha256 !== sha256)
    throw new ReleaseError("Контрольная сумма не совпала: файл повреждён при передаче. Загрузите его ещё раз.", 422);

  const id = crypto.randomUUID();
  const release: AppRelease = {
    id,
    platform: data.platform,
    channel: data.channel,
    version: data.version,
    arch: data.arch,
    file_name: upload.name.replaceAll(/[\\/]/g, "_"),
    size_bytes: upload.size,
    sha256,
    min_os_version: data.min_os_version,
    release_notes: data.release_notes,
    mandatory: data.mandatory,
    status: "draft",
    rollout_percent: 100,
    downloads: 0,
    uploaded_by: DEMO_UPLOADER,
    uploaded_at: new Date().toISOString(),
    published_at: null,
    revoked_at: null,
    download_url: `/api/admin/apps/releases/${id}/download`,
  };
  files.set(id, upload);
  store.set(id, { release, hasFile: true });
  return release;
}

/* ---------- Status, rollout, delete ---------- */

export function updateRelease(id: string, patch: ReleasePatch): AppRelease {
  const stored = store.get(id);
  if (!stored) throw new ReleaseError("Сборка не найдена.", 404);
  let next = { ...stored.release };

  if (patch.status === "published") {
    if (next.status !== "draft") throw new ReleaseError("Опубликовать можно только черновик.", 409);
    next = { ...next, status: "published", published_at: new Date().toISOString() };
  } else if (patch.status === "revoked") {
    if (next.status !== "published") throw new ReleaseError("Отозвать можно только опубликованную сборку.", 409);
    next = { ...next, status: "revoked", revoked_at: new Date().toISOString() };
  }

  if (patch.rollout_percent !== undefined) {
    if (next.status !== "published" || next.channel !== "stable")
      throw new ReleaseError("Поэтапная раскатка доступна только для опубликованных стабильных сборок.", 409);
    next = { ...next, rollout_percent: patch.rollout_percent };
  }

  store.set(id, { ...stored, release: next });
  return next;
}

export function deleteRelease(id: string) {
  const stored = store.get(id);
  if (!stored) throw new ReleaseError("Сборка не найдена.", 404);
  if (stored.release.status !== "draft") throw new ReleaseError("Удалить можно только черновик.", 409);
  store.delete(id);
  files.delete(id);
}

/** Answers with a stored build; counts the download when the build is published. */
export function downloadRelease(id: string): Response {
  const stored = store.get(id);
  if (!stored) throw new ReleaseError("Сборка не найдена.", 404);
  if (!stored.hasFile) throw new ReleaseError("Это демонстрационная сборка: файл не загружался.", 404);
  const file = files.get(id);
  if (!file) throw new ReleaseError("Файл сборки не найден.", 404);

  const { release } = stored;
  if (release.status === "published")
    store.set(id, { ...stored, release: { ...release, downloads: release.downloads + 1 } });
  const ascii = release.file_name.replaceAll(/[^\x20-\x7e]|"/g, "_");
  return new Response(file, {
    headers: {
      "content-type": "application/octet-stream",
      "content-length": String(file.size),
      "content-disposition": `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(release.file_name)}`,
      "cache-control": "no-store",
    },
  });
}
