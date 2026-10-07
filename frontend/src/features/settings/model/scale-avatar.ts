import { AVATAR_SIZE } from "../domain/settings-contract";

/** Largest photo we'll try to read; anything bigger is almost certainly not a profile picture. */
export const AVATAR_INPUT_MAX_BYTES = 10 * 1024 * 1024;

/** Why a photo couldn't be prepared: a code the action words in the interface language. */
export type AvatarProblem = "tooLarge" | "unreadable" | "processFailed";

export class AvatarError extends Error {
  readonly problem: AvatarProblem;

  constructor(problem: AvatarProblem) {
    super(problem);
    this.name = "AvatarError";
    this.problem = problem;
  }
}

const toBlob = (canvas: HTMLCanvasElement, type: string) =>
  new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, 0.9));

/**
 * Crops a photo to its centre square and scales it to AVATAR_SIZE px a side, honouring EXIF
 * rotation. Returns WebP, or JPEG where the browser can't encode WebP. Throws an AvatarError when the
 * file is too large or the browser can't decode or encode it.
 */
export async function scaleAvatar(file: File): Promise<Blob> {
  if (file.size > AVATAR_INPUT_MAX_BYTES) throw new AvatarError("tooLarge");
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" }).catch(() => {
    throw new AvatarError("unreadable");
  });
  const side = Math.min(bitmap.width, bitmap.height);
  const canvas = document.createElement("canvas");
  canvas.width = AVATAR_SIZE;
  canvas.height = AVATAR_SIZE;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new AvatarError("processFailed");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(
    bitmap,
    (bitmap.width - side) / 2,
    (bitmap.height - side) / 2,
    side,
    side,
    0,
    0,
    AVATAR_SIZE,
    AVATAR_SIZE,
  );
  bitmap.close();
  const webp = await toBlob(canvas, "image/webp");
  // Browsers that can't encode WebP silently fall back to PNG; JPEG is far smaller for photos.
  if (webp?.type === "image/webp") return webp;
  const jpeg = await toBlob(canvas, "image/jpeg");
  if (!jpeg) throw new AvatarError("processFailed");
  return jpeg;
}
