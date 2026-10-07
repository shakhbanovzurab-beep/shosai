"use client";

import { useRef, useState } from "react";

import { useTranslations } from "next-intl";

import { errorMessage } from "@/lib/errors";

import { studioApi } from "../api/studio-api";
import type { SkillCandidate } from "../domain/contract";

type SearchState = { status: "idle" | "loading" | "done"; results: SkillCandidate[]; error: string | null };

/** Searches the skills.sh directory as you type, a short pause after the last keystroke. */
export function useDirectorySearch() {
  const t = useTranslations("studioSkills");
  const [state, setState] = useState<SearchState>({ status: "idle", results: [], error: null });
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const latest = useRef("");

  const search = (query: string) => {
    const q = query.trim();
    latest.current = q;
    clearTimeout(timer.current);
    if (q.length < 2) {
      setState({ status: "idle", results: [], error: null });
      return;
    }
    setState((prev) => ({ ...prev, status: "loading" }));
    timer.current = setTimeout(() => {
      studioApi.searchSkills(q).then(
        ({ results }) => {
          if (latest.current === q) setState({ status: "done", results, error: null });
        },
        (error: unknown) => {
          if (latest.current === q) {
            setState({ status: "done", results: [], error: errorMessage(error) ?? t("readyMade.searchFailed") });
          }
        },
      );
    }, 300);
  };

  return { state, search };
}
