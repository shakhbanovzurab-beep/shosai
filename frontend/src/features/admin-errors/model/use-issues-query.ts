"use client";

import { useSearchParams } from "@/lib/navigation";

import { type IssuesQuery, issuesQueryToParams, parseIssuesQuery } from "../domain/query";

/**
 * The list's filters, sort and page live in the URL so a view can be shared and survives going
 * back from an issue. Updates use the History API, which Next.js syncs with `useSearchParams`
 * without a server round trip.
 */
export function useIssuesQuery() {
  const searchParams = useSearchParams();
  const query = parseIssuesQuery(new URLSearchParams(searchParams.toString()));

  function setQuery(patch: Partial<IssuesQuery>) {
    // Any change other than paging starts again from the first page.
    const next = { ...query, page: 1, ...patch };
    const search = issuesQueryToParams(next).toString();
    window.history.replaceState(null, "", search ? `?${search}` : window.location.pathname);
  }

  return { query, setQuery };
}
