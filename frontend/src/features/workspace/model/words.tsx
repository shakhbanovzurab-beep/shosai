"use client";

import type { ReactNode } from "react";

import { useTranslations } from "next-intl";

/*
 * The catalogs the model's actions word their toasts with. Actions are plain functions, so the Client
 * Component that calls one passes its translator in (`useTranslations("workspace")`, or "workspaceMembers" for people and teams).
 */

export type WorkspaceWords = ReturnType<typeof useTranslations<"workspace">>;
export type MembersWords = ReturnType<typeof useTranslations<"workspaceMembers">>;
export type CommonWords = ReturnType<typeof useTranslations<"common">>;

type Say = (t: WorkspaceWords, common: CommonWords) => string;

function Words({ say }: { say: Say }) {
  const t = useTranslations("workspace");
  const common = useTranslations("common");
  return say(t, common);
}

/**
 * Words for a toast from an action whose callers don't pass a translator: rendered by the toaster, which
 * sits inside the language provider, so they follow the interface language. The meetings, tasks,
 * knowledge and project actions use it, as their callers live in parts of the slice localized separately.
 */
export const words = (say: Say): ReactNode => <Words say={say} />;

/** What a failed request says: the server words its refusals in the request's interface language. */
export const failureText = (error: unknown) => (error instanceof Error ? error.message : String(error));
