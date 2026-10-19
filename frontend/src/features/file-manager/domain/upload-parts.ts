/** A part of an upload as the server signs it: its number (from 1), its exact length and where to PUT it. */
export type PartLink = {
  number: number;
  size_bytes: number;
  url: string;
  headers: Record<string, string>;
};

/** Where each part's bytes lie in the file: parts follow each other in the order of their numbers. */
export function partRanges(parts: readonly Pick<PartLink, "number" | "size_bytes">[]): Map<number, [number, number]> {
  const ranges = new Map<number, [number, number]>();
  let start = 0;
  for (const part of parts.toSorted((a, b) => a.number - b.number)) {
    ranges.set(part.number, [start, start + part.size_bytes]);
    start += part.size_bytes;
  }
  return ranges;
}
