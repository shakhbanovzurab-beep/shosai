"use client";

import { useState } from "react";

import { CircleAlert } from "lucide-react";
import { useFormatter, useNow, useTranslations } from "next-intl";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { type AutosaveStatus, useAutosave } from "@/hooks/use-autosave";

import { CONTEXT_MAX_CHARS } from "../domain/contract";
import { approxTokens } from "../domain/models";
import { saveContext } from "../model/save-actions";

/** "Saved 5 minutes ago", brought up to date once a minute. */
function SavedAgo({ at }: { at: string }) {
  const t = useTranslations("studio");
  const format = useFormatter();
  const now = useNow({ updateInterval: 60_000 });
  // A save newer than the last tick reads "now", never "in 20 seconds".
  const saved = new Date(Math.min(Date.parse(at), now.getTime()));
  return t("context.savedAgo", { ago: format.relativeTime(saved, now) });
}

function SaveStatus({
  status,
  savedAt,
  onRetry,
}: {
  status: AutosaveStatus;
  savedAt: string | null;
  onRetry: () => void;
}) {
  const t = useTranslations("studio");
  const tc = useTranslations("common");
  if (status === "saving" || status === "pending") {
    return (
      <span className="flex items-center gap-1.5 text-muted-foreground" aria-live="polite">
        <Spinner className="size-3" />
        {t("autosave.saving")}
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="flex items-center gap-1.5 text-destructive" role="alert">
        <CircleAlert className="size-3.5" />
        {t("context.saveFailed")}
        <button type="button" className="underline underline-offset-2" onClick={onRetry}>
          {tc("actions.retry")}
        </button>
      </span>
    );
  }
  return (
    <span className="text-muted-foreground" aria-live="polite">
      {savedAt ? <SavedAgo at={savedAt} /> : t("context.savesAutomatically")}
    </span>
  );
}

type ContextEditorProps = { initialContent: string; savedAt: string | null };

/** The text sent as the first system message of every request. Saves itself as you type. */
export function ContextEditor({ initialContent, savedAt }: ContextEditorProps) {
  const t = useTranslations("studio");
  const [draft, setDraft] = useState(initialContent);
  const autosave = useAutosave(saveContext);
  const tooLong = draft.length > CONTEXT_MAX_CHARS;

  const change = (value: string) => {
    setDraft(value);
    // Over the limit stays local until it is trimmed back; the server would refuse it anyway.
    if (value.length <= CONTEXT_MAX_CHARS) autosave.schedule(value);
  };

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <CardTitle>
          <Label htmlFor="studio-context">{t("context.title")}</Label>
        </CardTitle>
        <CardDescription>{t("context.description")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <Textarea
          id="studio-context"
          dir="auto"
          value={draft}
          onChange={(event) => change(event.currentTarget.value)}
          onBlur={autosave.flush}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "s") {
              event.preventDefault();
              autosave.flush();
            }
          }}
          placeholder={t("context.example")}
          aria-invalid={tooLong}
          aria-describedby="studio-context-count"
          className="min-h-64 font-mono text-sm leading-6"
        />
        <div id="studio-context-count" className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <span className={tooLong ? "text-destructive" : "text-muted-foreground"}>
            {t("context.count", { count: draft.length, max: CONTEXT_MAX_CHARS, tokens: approxTokens(draft) })}
            {tooLong ? ` ${t("context.tooLong")}` : null}
          </span>
          <SaveStatus status={autosave.status} savedAt={savedAt} onRetry={autosave.flush} />
        </div>
      </CardContent>
    </Card>
  );
}
