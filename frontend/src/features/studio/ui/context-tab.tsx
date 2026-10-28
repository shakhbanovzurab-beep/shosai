"use client";

import { useState } from "react";

import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";

import { contextResource, useStudioContext } from "../model/studio-resources";
import { ContextEditor } from "./context-editor";
import { SystemMessagePreview } from "./system-message-preview";
import { TabIntro } from "./tab-intro";

/** Редактор и превью над одним черновиком: превью показывает текст, пока человек его пишет. */
function ContextWorkspace({ initialContent, savedAt }: { initialContent: string; savedAt: string | null }) {
  const [draft, setDraft] = useState(initialContent);
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <ContextEditor draft={draft} onDraftChange={setDraft} savedAt={savedAt} />
      <SystemMessagePreview content={draft} />
    </div>
  );
}

export function ContextTab() {
  const t = useTranslations("studio");
  const state = useStudioContext();

  return (
    <div className="flex flex-col gap-6">
      <TabIntro>{t("context.intro")}</TabIntro>
      {state.status === "loading" ? <Skeleton className="h-96 rounded-xl" /> : null}
      {state.status === "error" ? (
        <LoadError
          title={t("context.loadFailed")}
          message={state.message}
          onRetry={() => void contextResource.refresh()}
        />
      ) : null}
      {state.status === "ready" ? (
        <ContextWorkspace initialContent={state.data.content} savedAt={state.data.updated_at} />
      ) : null}
    </div>
  );
}
