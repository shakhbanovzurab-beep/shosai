"use client";

import { useState } from "react";

import { ChevronDown, ChevronUp, Search, X } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
  InputGroupText,
} from "@/components/ui/input-group";

import { markTranscript, transcriptMatchId } from "../domain/transcript-search";
import type { TranscriptLine } from "../domain/types";
import { NoteTranscript } from "./note-transcript";

function reveal(match: number) {
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
  document.getElementById(transcriptMatchId(match))?.scrollIntoView({ block: "center", behavior: motion });
}

interface TranscriptSearchProps {
  readonly lines: TranscriptLine[];
  readonly moment?: number;
}

/**
 * The transcript with a find bar: typing highlights every match, Enter and the arrows step through them
 * (Shift+Enter goes back), Escape clears.
 */
export function TranscriptSearch({ lines, moment }: TranscriptSearchProps) {
  const t = useTranslations("notesNote");
  const [query, setQuery] = useState("");
  // The match the user moved to; -1 until they move.
  const [current, setCurrent] = useState(-1);
  const searching = query.trim().length > 0;
  const { total } = markTranscript(lines, query);

  const step = (direction: 1 | -1) => {
    if (total === 0) return;
    const next = current === -1 && direction === -1 ? total - 1 : (current + direction + total) % total;
    setCurrent(next);
    reveal(next);
  };
  const clear = () => {
    setQuery("");
    setCurrent(-1);
  };

  const status =
    current === -1 || total === 0
      ? t("transcript.matches", { count: total })
      : t("transcript.position", { current: current + 1, total });

  return (
    <div className="flex flex-col gap-5">
      <search>
        <InputGroup>
          <InputGroupAddon>
            <Search />
          </InputGroupAddon>
          <InputGroupInput
            type="search"
            name="transcript-search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setCurrent(-1);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                step(event.shiftKey ? -1 : 1);
              }
              if (event.key === "Escape" && query) {
                event.preventDefault();
                clear();
              }
            }}
            dir="auto"
            placeholder={t("transcript.searchPlaceholder")}
            aria-label={t("transcript.search")}
            autoComplete="off"
            className="[&::-webkit-search-cancel-button]:appearance-none"
          />
          {searching ? (
            <InputGroupAddon align="inline-end">
              <InputGroupText className="tabular-nums" aria-live="polite">
                {status}
              </InputGroupText>
              <InputGroupButton
                size="icon-xs"
                aria-label={t("transcript.previous")}
                disabled={total === 0}
                onClick={() => step(-1)}
              >
                <ChevronUp />
              </InputGroupButton>
              <InputGroupButton
                size="icon-xs"
                aria-label={t("transcript.next")}
                disabled={total === 0}
                onClick={() => step(1)}
              >
                <ChevronDown />
              </InputGroupButton>
              <InputGroupButton size="icon-xs" aria-label={t("transcript.clear")} onClick={clear}>
                <X />
              </InputGroupButton>
            </InputGroupAddon>
          ) : null}
        </InputGroup>
      </search>
      <NoteTranscript lines={lines} moment={moment} search={searching ? { query, current } : undefined} />
    </div>
  );
}
