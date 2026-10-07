import { createHash } from "node:crypto";
import { createWriteStream, type WriteStream } from "node:fs";

/** A failure with the HTTP status the route should answer with. */
export class ReleaseError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

/* A streaming multipart/form-data reader for the demo upload, so a large build never sits in memory. */

export type ReceivedFile = { fileName: string; size: number; sha256: string };

/** Pulls `name` and `filename` out of a part's Content-Disposition header. */
function parseDisposition(headers: string) {
  const line = headers.split("\r\n").find((h) => h.toLowerCase().startsWith("content-disposition:")) ?? "";
  const name = /;\s*name="([^"]*)"/i.exec(line)?.[1] ?? "";
  const fileName = /;\s*filename="([^"]*)"/i.exec(line)?.[1];
  return { name, fileName: fileName === undefined ? null : fileName.replaceAll(/[\\/]/g, "_") };
}

async function write(stream: WriteStream, data: Buffer) {
  if (stream.write(data)) return;
  await new Promise<void>((resolve, reject) => {
    stream.once("drain", resolve);
    stream.once("error", reject);
  });
}

const closeStream = (stream: WriteStream) =>
  new Promise<void>((resolve, reject) => {
    stream.once("error", reject);
    stream.end(resolve);
  });

/**
 * Reads the multipart body chunk by chunk. Text fields are collected (up to 64 KB); the `file` part is
 * written to `target` and hashed on the way. `onField` runs as soon as a field is complete, so the
 * metadata (sent first) is validated before a single byte of the build is stored.
 */
export async function receiveMultipart(
  body: ReadableStream<Uint8Array>,
  boundary: string,
  target: string,
  maxFileBytes: number,
  onField: (name: string, value: string) => void,
): Promise<ReceivedFile> {
  const opening = Buffer.from(`--${boundary}`);
  const delimiter = Buffer.from(`\r\n--${boundary}`);
  const headerEnd = Buffer.from("\r\n\r\n");
  const reader = body.getReader();

  let buffer = Buffer.alloc(0);
  // Cast so TypeScript doesn't narrow it: the parsing closure changes it.
  let state = "preamble" as "preamble" | "boundary" | "headers" | "body" | "done";
  let part: { name: string; fileName: string | null } | null = null;
  let field: Buffer[] = [];
  let fieldSize = 0;
  let sink: WriteStream | null = null;
  const hash = createHash("sha256");
  // A holder rather than a `let`: it is set inside the callbacks, which TypeScript's narrowing can't see.
  const out: { file: ReceivedFile | null } = { file: null };
  let fileSize = 0;

  const take = async (data: Buffer) => {
    if (data.length === 0 || part === null) return;
    if (part.fileName === null) {
      fieldSize += data.length;
      if (fieldSize > 64 * 1024) throw new ReleaseError("Поле формы слишком большое.", 413);
      field.push(data);
      return;
    }
    fileSize += data.length;
    if (fileSize > maxFileBytes) throw new ReleaseError("Файл больше допустимого размера.", 413);
    hash.update(data);
    if (sink) await write(sink, data);
  };

  const finishPart = async () => {
    if (part === null) return;
    if (part.fileName === null) {
      onField(part.name, Buffer.concat(field).toString("utf8"));
    } else if (sink) {
      await closeStream(sink);
      sink = null;
      out.file = { fileName: part.fileName, size: fileSize, sha256: hash.digest("hex") };
    }
    part = null;
  };

  const process = async () => {
    for (;;) {
      if (state === "preamble") {
        const at = buffer.indexOf(opening);
        if (at === -1) return;
        buffer = buffer.subarray(at + opening.length);
        state = "boundary";
      } else if (state === "boundary") {
        if (buffer.length < 2) return;
        if (buffer[0] === 0x2d && buffer[1] === 0x2d) {
          state = "done";
          return;
        }
        if (buffer[0] !== 0x0d || buffer[1] !== 0x0a) throw new ReleaseError("Повреждённый запрос.", 400);
        buffer = buffer.subarray(2);
        state = "headers";
      } else if (state === "headers") {
        const at = buffer.indexOf(headerEnd);
        if (at === -1) {
          if (buffer.length > 16 * 1024) throw new ReleaseError("Повреждённый запрос.", 400);
          return;
        }
        part = parseDisposition(buffer.subarray(0, at).toString("utf8"));
        buffer = buffer.subarray(at + headerEnd.length);
        if (part.fileName !== null) {
          if (part.name !== "file" || out.file !== null || sink !== null)
            throw new ReleaseError("Прикрепите одну сборку в поле `file`.", 422);
          sink = createWriteStream(target);
        } else {
          field = [];
          fieldSize = 0;
        }
        state = "body";
      } else if (state === "body") {
        const at = buffer.indexOf(delimiter);
        if (at === -1) {
          // Keep enough of the tail to spot a delimiter split across chunks.
          const safe = buffer.length - (delimiter.length - 1);
          if (safe > 0) {
            await take(buffer.subarray(0, safe));
            buffer = buffer.subarray(safe);
          }
          return;
        }
        await take(buffer.subarray(0, at));
        buffer = buffer.subarray(at + delimiter.length);
        await finishPart();
        state = "boundary";
      } else {
        return;
      }
    }
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer = buffer.length === 0 ? Buffer.from(value) : Buffer.concat([buffer, value]);
      await process();
      if (state === "done") break;
    }
    if (state !== "done") throw new ReleaseError("Загрузка прервалась.", 400);
    if (out.file === null) throw new ReleaseError("Прикрепите сборку в поле `file`.", 422);
    return out.file;
  } catch (error) {
    // Typed as `never` by the narrowing above; the callbacks may have opened it.
    (sink as WriteStream | null)?.destroy();
    await reader.cancel().catch(() => undefined);
    throw error;
  }
}
