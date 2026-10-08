import { cn } from "cn";
import { useTranslations } from "use-intl";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { getInitials } from "@/lib/utils";

import { formatTimestamp } from "../domain/format";
import { markTranscript, type TranscriptSegment, transcriptMatchId } from "../domain/transcript-search";
import type { TranscriptLine } from "../domain/types";
import { MomentScroll } from "./moment-scroll";

/** The line playing at `moment` seconds: the last one that started by then. */
const lineAt = (lines: TranscriptLine[], moment: number) => lines.findLast((line) => line.at <= moment);

interface NoteTranscriptProps {
  readonly lines: TranscriptLine[];
  readonly moment?: number;
  /** A search to highlight: every match, and the one the user moved to (-1 for none yet). */
  readonly search?: { readonly query: string; readonly current: number };
}

/** What was said, line by line; speakers' names and words keep their own direction in any interface language. */
export function NoteTranscript({ lines, moment, search }: NoteTranscriptProps) {
  const t = useTranslations("notesNote");
  const current = moment === undefined ? undefined : lineAt(lines, moment);
  const marked = markTranscript(lines, search?.query ?? "");
  return (
    <ol className="flex flex-col gap-5" aria-label={t("transcript.label")}>
      {marked.lines.map(({ line, segments }) => {
        const here = line === current;
        return (
          <li
            key={`${line.speaker}-${line.at}`}
            id={here ? "transcript-moment" : undefined}
            aria-current={here ? "time" : undefined}
            className={cn("flex scroll-mt-24 gap-3", here && "-mx-3 rounded-lg bg-muted px-3 py-2")}
          >
            <Avatar size="sm" className="mt-0.5">
              <AvatarFallback className="text-[10px]">{getInitials(line.speaker)}</AvatarFallback>
            </Avatar>
            <div className="flex min-w-0 flex-col gap-1">
              <div className="flex items-baseline gap-2">
                <span dir="auto" className="font-medium text-sm">
                  {line.speaker}
                </span>
                <time className="font-mono text-muted-foreground text-xs tabular-nums" dateTime={`PT${line.at}S`}>
                  {formatTimestamp(line.at)}
                </time>
              </div>
              <p dir="auto" className="text-sm leading-relaxed">
                {segments.map((segment) => (
                  <Segment key={segment.start} segment={segment} current={search?.current ?? -1} />
                ))}
              </p>
            </div>
          </li>
        );
      })}
      {current ? <MomentScroll /> : null}
    </ol>
  );
}

function Segment({ segment, current }: { readonly segment: TranscriptSegment; readonly current: number }) {
  if (segment.match === null) return segment.text;
  return (
    <mark
      id={transcriptMatchId(segment.match)}
      className={cn(
        "scroll-mt-24 rounded-sm text-foreground",
        segment.match === current ? "bg-primary text-primary-foreground" : "bg-primary/15",
      )}
    >
      {segment.text}
    </mark>
  );
}
