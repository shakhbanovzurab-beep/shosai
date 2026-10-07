"use client";

import Link from "next/link";

import { Plus, Settings2, UserPlus } from "lucide-react";
import { useTranslations } from "next-intl";

import { DropdownMenuGroup, DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { WorkspaceSummary } from "../../domain/contract";
import { NEW_WORKSPACE_PATH, workspacePath } from "../../domain/paths";
import { permissionsOf } from "../../domain/roles";
import { openInviteDialog } from "../../model/invite-dialog-store";
import { resourcesOf } from "../../model/resources";

/** Invite and settings for the workspace open now, when the member may; then starting a new workspace. */
function CurrentWorkspaceActions({ current }: { current: WorkspaceSummary }) {
  const t = useTranslations("workspace");
  const state = usePollingResource(resourcesOf(current.id).state);
  const can = state.status === "ready" ? permissionsOf(state.data) : null;
  if (!can?.invite && !can?.editSettings) return null;
  return (
    <>
      {can.invite ? (
        <DropdownMenuItem onSelect={openInviteDialog}>
          <UserPlus />
          <span dir="auto">{t("switcher.invite", { name: current.name })}</span>
        </DropdownMenuItem>
      ) : null}
      {can.editSettings ? (
        <DropdownMenuItem asChild>
          <Link href={workspacePath(current.slug, "/settings")}>
            <Settings2 />
            {t("switcher.settings")}
          </Link>
        </DropdownMenuItem>
      ) : null}
    </>
  );
}

export function SwitcherActions({ current }: { current: WorkspaceSummary | null }) {
  const t = useTranslations("workspace");
  return (
    <>
      <DropdownMenuSeparator />
      <DropdownMenuGroup>
        {/* A suspended workspace has nothing to invite to or set up until it's restored. */}
        {current && !current.suspended ? <CurrentWorkspaceActions current={current} /> : null}
        <DropdownMenuItem asChild>
          <Link href={NEW_WORKSPACE_PATH}>
            <Plus />
            {t("createWorkspace")}
          </Link>
        </DropdownMenuItem>
      </DropdownMenuGroup>
    </>
  );
}
