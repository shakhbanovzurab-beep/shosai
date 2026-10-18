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

/** How far a batch got, in percent of its bytes, from what each file has sent so far. */
export function batchPercent(sent: readonly number[], sizes: readonly number[]): number {
  const total = sizes.reduce((sum, size) => sum + size, 0);
  if (total === 0) return 0;
  const done = sent.reduce((sum, bytes, index) => sum + Math.min(bytes, sizes[index] ?? 0), 0);
  return Math.min(100, Math.floor((done / total) * 100));
}
