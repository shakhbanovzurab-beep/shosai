"use client";

import { useEffect, useRef } from "react";

import { useLocale } from "use-intl";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { insightsApi } from "../api/insights-api";
import { buildLeoViews, type LeoMailView } from "../domain/leo-triage";
import { useLeoOverrides } from "./leo-store";

/** Leo's reading of the inbox. It keeps polling while Leo is still reading new emails. */
export const insightsResource = createPollingResource(insightsApi.list, (data) =>
  data.insights.some((insight) => insight.status === "analyzing"),
);

const NO_VIEWS: ReadonlyMap<string, LeoMailView> = new Map();

/** Leo's reading of every email, with the user's corrections and draft edits applied. */
export function useLeoInbox() {
  const state = usePollingResource(insightsResource);
  const overrides = useLeoOverrides();
  useRereadOnLanguageChange();
  const views: ReadonlyMap<string, LeoMailView> =
    state.status === "ready" ? buildLeoViews(state.data.insights, overrides) : NO_VIEWS;

  return { state, views };
}

/* Leo writes its summaries and drafts in the user's language, and the backend learns it from each request
   (`Accept-Language`, see server/insights-route.ts). Switching the interface language fetches them again. */
function useRereadOnLanguageChange() {
  const locale = useLocale();
  const readIn = useRef(locale);
  useEffect(() => {
    if (readIn.current === locale) return;
    readIn.current = locale;
    void insightsResource.refresh();
  }, [locale]);
}
