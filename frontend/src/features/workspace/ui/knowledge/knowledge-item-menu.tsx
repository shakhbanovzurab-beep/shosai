"use client";

import { type ReactNode, useState } from "react";

import { EllipsisVertical, ExternalLink, FolderKanban, Trash2, Undo2, Unplug, Users } from "lucide-react";
import { useTranslations } from "use-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu-items";
import { DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger } from "@/components/ui/dropdown-menu-sub";

import type { KnowledgeItem } from "../../domain/knowledge-contract";
import { accessKey, parseAccessKey } from "../../domain/visibility";
import { changeKnowledge, removeKnowledge } from "../../model/knowledge-actions";
import type { KnowledgeCtx } from "./knowledge-row";
import { accessChoices, accessText, type KnowledgeWords, type Who } from "./knowledge-words";

const NO_PROJECT = "none";

type Removal = { label: string; icon: ReactNode; title: string; text: string };

/** How removing reads for each kind of knowledge: an upload, a source, or someone's shared file. */
function removal(t: KnowledgeWords, remove: string, item: KnowledgeItem, who: Who, workspace: string): Removal {
  const name = item.name;
  if (item.source.kind === "personal")
    return {
      label: t("remove.stopSharing"),
      icon: <Undo2 className="rtl:-scale-x-100" />,
      title: t("remove.stopSharingTitle", { name }),
      text: t("remove.stopSharingText", { ...who, workspace }),
    };
  if (item.source.kind === "connector")
    return {
      label: t("remove.disconnect"),
      icon: <Unplug />,
      title: t("remove.disconnectTitle", { name }),
      text: t("remove.disconnectText", { provider: t(`kind.${item.source.provider}`) }),
    };
  return {
    label: remove,
    icon: <Trash2 />,
    title: t("remove.removeTitle", { name }),
    text: t("remove.removeText", { workspace }),
  };
}

/** Who can use it, the project it belongs to, and removing it; for whoever added it, and admins. */
export function KnowledgeItemMenu({ item, ctx, who }: { item: KnowledgeItem; ctx: KnowledgeCtx; who: Who }) {
  const t = useTranslations("workspaceKnowledge");
  const common = useTranslations("common");
  const [confirming, setConfirming] = useState(false);
  const { ws, teams, workspaceName } = ctx;
  const remove = removal(t, common("actions.remove"), item, who, workspaceName);
  const projects = ctx.projects.filter((p) => p.status !== "completed" || p.id === item.project_id);
  const source = item.source.kind === "connector" ? item.source : null;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={common("actionsFor", { name: item.name })}>
            <EllipsisVertical />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuGroup>
            {source?.url ? (
              <DropdownMenuItem asChild>
                <a href={source.url} target="_blank" rel="noreferrer">
                  <ExternalLink className="rtl:-scale-x-100" />
                  {t("menu.openIn", { provider: t(`kind.${source.provider}`) })}
                </a>
              </DropdownMenuItem>
            ) : null}
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>
                <Users />
                {t("access.label")}
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="w-52">
                <DropdownMenuRadioGroup
                  value={accessKey(item.access)}
                  onValueChange={(key) => {
                    const access = parseAccessKey(key);
                    const phrase =
                      access.level === "team"
                        ? t("changed.team", { team: accessText(t, access, teams, workspaceName) })
                        : t("changed.everyone", { workspace: workspaceName });
                    void changeKnowledge(ws, item, { access }, phrase);
                  }}
                >
                  {accessChoices(t, teams, workspaceName, ctx.me, ctx.admin).map((option) => (
                    <DropdownMenuRadioItem key={option.key} value={option.key}>
                      <span dir="auto">{option.label}</span>
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuSubContent>
            </DropdownMenuSub>
            {projects.length > 0 ? (
              <DropdownMenuSub>
                <DropdownMenuSubTrigger>
                  <FolderKanban />
                  {t("menu.project")}
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent className="w-52">
                  <DropdownMenuRadioGroup
                    value={item.project_id ?? NO_PROJECT}
                    onValueChange={(key) => {
                      const project = projects.find((p) => p.id === key);
                      const phrase = project
                        ? t("changed.addedToProject", { project: project.name })
                        : t("changed.noProject");
                      void changeKnowledge(ws, item, { project_id: project?.id ?? null }, phrase);
                    }}
                  >
                    <DropdownMenuRadioItem value={NO_PROJECT}>{t("menu.noProject")}</DropdownMenuRadioItem>
                    {projects.map((p) => (
                      <DropdownMenuRadioItem key={p.id} value={p.id}>
                        <span dir="auto">{p.name}</span>
                      </DropdownMenuRadioItem>
                    ))}
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuSub>
            ) : null}
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem variant="destructive" onSelect={() => setConfirming(true)}>
              {remove.icon}
              {remove.label}
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <ConfirmDestructive
        open={confirming}
        title={remove.title}
        description={remove.text}
        confirmLabel={remove.label}
        onConfirm={() => {
          setConfirming(false);
          void removeKnowledge(ws, item);
        }}
        onCancel={() => setConfirming(false)}
      />
    </>
  );
}
