"use client";

import { useTranslations } from "next-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";

import { contextResource, useStudioContext } from "../model/studio-resources";
import { ContextEditor } from "./context-editor";
import { SystemMessagePreview } from "./system-message-preview";
import { TabIntro } from "./tab-intro";

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
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <ContextEditor initialContent={state.data.content} savedAt={state.data.updated_at} />
          <SystemMessagePreview content={state.data.content} />
        </div>
      ) : null}
    </div>
  );
}
