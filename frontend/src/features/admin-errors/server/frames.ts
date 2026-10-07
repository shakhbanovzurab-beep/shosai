import type { StackFrame } from "../domain/contract";
import type { FrameSeed } from "./types";

/** Deterministic PRNG so the demo looks the same on every reload. */
export function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4_294_967_296;
  };
}

/** FNV-1a, as short hex: stable ids and fingerprints from text. */
export function hash(text: string) {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, "0");
}

export const compareVersions = (a: string, b: string) => a.localeCompare(b, "en", { numeric: true });

/** Seed frames to stack frames; the source context goes on the top in-app frame. */
export function toFrames(seeds: FrameSeed[], context?: string[]): StackFrame[] {
  let contextUsed = false;
  return seeds.map(([fn, file, line, inApp]) => {
    const withContext = inApp && !contextUsed && context !== undefined;
    if (withContext) contextUsed = true;
    const start = line - Math.floor((context?.length ?? 0) / 2);
    return {
      function: fn,
      file,
      line,
      column: null,
      in_app: inApp,
      context: withContext ? context.map((code, index) => ({ line: start + index, code })) : null,
    };
  });
}

/** The top in-app frame as "function (file)". */
export function culpritOf(frames: StackFrame[]) {
  const top = frames.find((frame) => frame.in_app) ?? frames[0];
  if (!top) return "—";
  const file = top.file.split("/").at(-1) ?? top.file;
  return `${top.function} (${file})`;
}

const FRAME_PATTERN =
  /^(?:\d+\s+)?(?:at\s+)?(.+?)\s*(?:\(|\s+in\s+|\s+@\s+)([^\s()]+?):(?:line\s+)?(\d+)(?::(\d+))?\)?$/;
const SYSTEM_CODE =
  /node_modules|site-packages|\/usr\/lib|^System\.|^Microsoft\.|libdispatch|libswift|Foundation|CoreData|AppKit|ntdll|kernel32/i;

/** Parses a raw stack trace, one frame per line; lines that don't look like a frame are kept as-is. */
export function parseStack(stack: string): StackFrame[] {
  return stack
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .slice(0, 100)
    .map((line) => {
      const match = FRAME_PATTERN.exec(line);
      const fn = match?.[1] ?? line;
      const file = match?.[2] ?? "?";
      return {
        function: fn,
        file,
        line: match ? Number(match[3]) : 0,
        column: match?.[4] ? Number(match[4]) : null,
        in_app: Boolean(match) && !SYSTEM_CODE.test(`${fn} ${file}`),
        context: null,
      };
    });
}
