import type { TranscriptLine } from "./types";

/** A piece of a line's text: plain, or the n-th search match in reading order across the whole transcript. */
export interface TranscriptSegment {
  /** Where the piece starts in the line's text. */
  start: number;
  text: string;
  match: number | null;
}

export interface MarkedLine {
  line: TranscriptLine;
  segments: TranscriptSegment[];
}

const REGEXP_SPECIALS = /[.*+?^${}()|[\]\\]/g;

/** The DOM id of the n-th search match, to scroll it into view. */
export const transcriptMatchId = (match: number) => `transcript-match-${match}`;

/** The transcript with every case-insensitive occurrence of the query marked, and how many there are. */
export function markTranscript(lines: TranscriptLine[], query: string): { lines: MarkedLine[]; total: number } {
  const needle = query.trim();
  if (!needle) {
    return { lines: lines.map((line) => ({ line, segments: [{ start: 0, text: line.text, match: null }] })), total: 0 };
  }

  // Запрос экранирован целиком (REGEXP_SPECIALS), поэтому выражение — буквальная строка без ReDoS.
  // nosemgrep: javascript.lang.security.audit.detect-non-literal-regexp.detect-non-literal-regexp
  const pattern = new RegExp(needle.replace(REGEXP_SPECIALS, "\\$&"), "giu");
  let total = 0;
  const marked = lines.map((line) => {
    const segments: TranscriptSegment[] = [];
    let from = 0;
    for (const found of line.text.matchAll(pattern)) {
      const at = found.index ?? 0;
      if (at > from) segments.push({ start: from, text: line.text.slice(from, at), match: null });
      segments.push({ start: at, text: found[0], match: total });
      total += 1;
      from = at + found[0].length;
    }
    if (from < line.text.length) segments.push({ start: from, text: line.text.slice(from), match: null });
    return { line, segments };
  });
  return { lines: marked, total };
}
