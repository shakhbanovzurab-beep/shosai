"use client";

import { useState } from "react";

import { useTranslations } from "use-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { useRouter } from "@/lib/navigation";

import { useWorkspace } from "../../model/use-workspace";
import { deleteWorkspace, leaveWorkspace } from "../../model/workspace-actions";
import { SettingRow } from "./setting-row";

/** Leaving (anyone but the owner) or deleting the workspace (the owner), each confirmed with its consequences. */
export function DangerZone() {
  const t = useTranslations("workspaceSettings");
  const shared = useTranslations("workspace");
  const { ws, state, can } = useWorkspace();
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const name = state.workspace.name;

  const deleting = can.deleteWorkspace;
  const words = deleting
    ? {
        title: t("danger.deleteTitle", { name }),
        description: t("danger.deleteDescription"),
        action: t("danger.delete"),
        hint: t("danger.deleteHint"),
        confirm: t("danger.delete"),
      }
    : {
        title: t("danger.leaveTitle", { name }),
        description: t("danger.leaveDescription"),
        action: t("danger.leave"),
        hint: t("danger.leaveHint"),
        confirm: t("danger.leaveConfirm"),
      };

  return (
    <section
      id="danger"
      aria-label={words.action}
      className="scroll-mt-20 rounded-xl border border-destructive/30 bg-card px-5 py-4"
    >
      <SettingRow title={words.action} description={words.hint}>
        <Button variant="destructive" onClick={() => setConfirming(true)}>
          {words.action}
        </Button>
      </SettingRow>
      <ConfirmDestructive
        open={confirming}
        title={words.title}
        description={words.description}
        confirmLabel={words.confirm}
        onConfirm={async () => {
          setConfirming(false);
          const done = deleting ? await deleteWorkspace(ws, name, shared) : await leaveWorkspace(ws, name, shared);
          if (done) router.push("/app/productivity");
        }}
        onCancel={() => setConfirming(false)}
      />
    </section>
  );
}
