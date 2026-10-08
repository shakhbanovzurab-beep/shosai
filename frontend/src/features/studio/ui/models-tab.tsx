"use client";

import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";

import { ROLES } from "../domain/roles";
import { modelsResource, useStudioModels } from "../model/studio-resources";
import { RoleModelRow } from "./role-model-row";
import { TabIntro } from "./tab-intro";

export function ModelsTab() {
  const t = useTranslations("studio");
  const state = useStudioModels();

  return (
    <div className="flex flex-col gap-6">
      <TabIntro>{t("models.intro")}</TabIntro>
      {state.status === "loading" ? <Skeleton className="h-[36rem] rounded-xl" /> : null}
      {state.status === "error" ? (
        <LoadError
          title={t("models.loadFailed")}
          message={state.message}
          onRetry={() => void modelsResource.refresh()}
        />
      ) : null}
      {state.status === "ready" ? (
        <div className="divide-y overflow-hidden rounded-xl border bg-card shadow-xs">
          {ROLES.map((role) => {
            const settings = state.data.roles.find((r) => r.role === role.id);
            return settings ? (
              <RoleModelRow key={role.id} role={role} settings={settings} models={state.data.models} />
            ) : null;
          })}
        </div>
      ) : null}
    </div>
  );
}
