"use client";

import { useState, useTransition } from "react";

import { Package, RefreshCw, Trash2, TriangleAlert } from "lucide-react";
import { useTranslations } from "use-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import type { Skill } from "../domain/contract";
import { uninstallSkill, updateSkill } from "../model/skill-actions";

function MineRow({ skill, onRemove }: { skill: Skill; onRemove: () => void }) {
  const t = useTranslations("studioSkills");
  const [updating, startUpdate] = useTransition();

  const update = () =>
    startUpdate(async () => {
      await updateSkill(skill, t);
    });

  return (
    <li className="flex items-start gap-3 rounded-xl border p-4">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span dir="auto" className="truncate font-medium font-mono">
          {skill.name}
        </span>
        <a
          href={skill.source_url}
          target="_blank"
          rel="noreferrer"
          dir="auto"
          className="truncate text-muted-foreground text-xs hover:text-foreground"
        >
          {skill.reference}
          {skill.commit ? ` · ${skill.commit}` : null}
        </a>
        <p dir="auto" className="line-clamp-3 text-muted-foreground text-sm">
          {skill.description}
        </p>
        {skill.has_extra_files ? (
          <p className="flex items-center gap-1.5 text-amber-700 text-xs dark:text-amber-400">
            <TriangleAlert className="size-3.5" aria-hidden="true" />
            {t("mine.extraFiles")}
          </p>
        ) : null}
      </div>
      <div className="flex shrink-0 flex-col gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("mine.update", { name: skill.name })}
              disabled={updating}
              onClick={update}
            >
              {updating ? <Spinner /> : <RefreshCw />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("mine.updateHint")}</TooltipContent>
        </Tooltip>
        <Button variant="ghost" size="icon-sm" aria-label={t("mine.remove", { name: skill.name })} onClick={onRemove}>
          <Trash2 />
        </Button>
      </div>
    </li>
  );
}

export function SkillsMine({ skills }: { skills: Skill[] }) {
  const t = useTranslations("studioSkills");
  const tc = useTranslations("common");
  const [removing, setRemoving] = useState<Skill | null>(null);

  if (skills.length === 0) {
    return (
      <Empty className="py-6">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Package />
          </EmptyMedia>
          <EmptyTitle>{t("mine.emptyTitle")}</EmptyTitle>
          <EmptyDescription>{t("mine.emptyDescription")}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }

  return (
    <>
      <ul className="flex flex-col gap-2">
        {skills.map((skill) => (
          <MineRow key={skill.id} skill={skill} onRemove={() => setRemoving(skill)} />
        ))}
      </ul>
      <ConfirmDestructive
        open={removing !== null}
        // The unnamed title only shows while the dialog fades out after closing.
        title={removing ? t("remove.title", { name: removing.name }) : t("remove.titleUnnamed")}
        description={t("remove.description")}
        confirmLabel={tc("actions.remove")}
        onConfirm={() => removing && void uninstallSkill(removing, t)}
        onCancel={() => setRemoving(null)}
      />
    </>
  );
}
