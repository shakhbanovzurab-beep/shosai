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
import { ReleaseError, receiveMultipart } from "./multipart";
import { createReadStream } from "node:fs";
import { mkdir, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";

/*
 * Demo store for desktop app releases, used when BACKEND_API_URL isn't set.
 * Metadata lives in memory (lost on restart). Uploaded files are streamed straight to
 * `${os.tmpdir()}/leo-app-releases/<id>` while their SHA-256 is computed, so a 500 MB build never
 * sits in memory. Seeded releases have metadata only; downloading them answers 404.
 */

const FILES_DIR = join(tmpdir(), "leo-app-releases");

const shared = globalThis as typeof globalThis & { adminDemoAppReleases?: Map<string, Stored> };
shared.adminDemoAppReleases ??= seedReleases();
const store = shared.adminDemoAppReleases;

const filePath = (id: string) => join(FILES_DIR, id);

export const listReleases = () =>
  [...store.values()].map((s) => s.release).toSorted((a, b) => b.uploaded_at.localeCompare(a.uploaded_at));

/** The public «latest» answer computed from the demo store. */
export const latestRelease = (
  platform: AppPlatform,
  channel: ReleaseChannel,
  arch: AppArch | null,
  installId: string | null,
) => latestFrom(listReleases(), platform, channel, arch, installId);

/** Receives POST /admin/apps/releases and stores it as a draft. Throws ReleaseError on any problem. */
export async function createRelease(request: Request): Promise<AppRelease> {
  const declared = Number(request.headers.get("content-length") ?? 0);
  if (declared > RELEASE_MAX_BYTES + 1024 * 1024) throw new ReleaseError("Файл больше 500 МБ.", 413);
  const boundary = /boundary=(?:"([^"]+)"|([^;]+))/i.exec(request.headers.get("content-type") ?? "");
  if (!boundary || !request.body) throw new ReleaseError("Отправьте форму multipart/form-data.", 415);

  const id = crypto.randomUUID();
  const target = filePath(id);
  let meta: ReleaseMetadata | null = null;

  try {
    await mkdir(FILES_DIR, { recursive: true });
    const file = await receiveMultipart(
      request.body,
      boundary[1] ?? boundary[2] ?? "",
      target,
      RELEASE_MAX_BYTES,
      (name, value) => {
        if (name !== "metadata") return;
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
        meta = parsed.data;
      },
    );

    const data = meta as ReleaseMetadata | null;
    if (data === null) throw new ReleaseError("Отправьте поле `metadata` перед файлом.", 422);
    // The platform may be overridden (e.g. a portable .zip for Windows), so any accepted type will do.
    if (!ACCEPTED_EXTENSIONS.includes(fileExtension(file.fileName)))
      throw new ReleaseError(`Подходят файлы ${ACCEPTED_EXTENSIONS.join(", ")}.`, 422);
    if (file.size === 0) throw new ReleaseError("Файл пустой.", 422);
    if (data.sha256 !== null && data.sha256 !== file.sha256)
      throw new ReleaseError("Контрольная сумма не совпала: файл повреждён при передаче. Загрузите его ещё раз.", 422);
    // Another upload may have taken the version while this one streamed.
    const problem = versionProblem(listReleases(), data);
    if (problem) throw new ReleaseError(problem, 409);

    const release: AppRelease = {
      id,
      platform: data.platform,
      channel: data.channel,
      version: data.version,
      arch: data.arch,
      file_name: file.fileName,
      size_bytes: file.size,
      sha256: file.sha256,
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
    store.set(id, { release, hasFile: true });
    return release;
  } catch (error) {
    await rm(target, { force: true });
    throw error;
  }
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

export async function deleteRelease(id: string) {
  const stored = store.get(id);
  if (!stored) throw new ReleaseError("Сборка не найдена.", 404);
  if (stored.release.status !== "draft") throw new ReleaseError("Удалить можно только черновик.", 409);
  store.delete(id);
  await rm(filePath(id), { force: true });
}

/** Streams a stored build from disk; counts the download when the build is published. */
export async function downloadRelease(id: string): Promise<Response> {
  const stored = store.get(id);
  if (!stored) throw new ReleaseError("Сборка не найдена.", 404);
  if (!stored.hasFile) throw new ReleaseError("Это демонстрационная сборка: файл не загружался.", 404);
  const path = filePath(id);
  const info = await stat(path).catch(() => null);
  if (!info) throw new ReleaseError("Файл сборки не найден на сервере.", 404);

  const { release } = stored;
  if (release.status === "published")
    store.set(id, { ...stored, release: { ...release, downloads: release.downloads + 1 } });
  const ascii = release.file_name.replaceAll(/[^\x20-\x7e]|"/g, "_");
  return new Response(Readable.toWeb(createReadStream(path)) as ReadableStream<Uint8Array>, {
    headers: {
      "content-type": "application/octet-stream",
      "content-length": String(info.size),
      "content-disposition": `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(release.file_name)}`,
      "cache-control": "no-store",
    },
  });
}
