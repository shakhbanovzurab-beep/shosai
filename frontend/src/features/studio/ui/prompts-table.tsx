"use client";

import { Check, Copy, Pencil, Trash2, Zap, ZapOff } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { contextKit } from "@/components/menu-kit";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from "@/components/ui/context-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { Prompt, PromptsResponse, Skill } from "../domain/contract";
import { setPromptInUse } from "../model/prompt-actions";

const K = contextKit;

export type PromptRowActions = {
  edit: (p: Prompt) => void;
  duplicate: (p: Prompt) => void;
  remove: (p: Prompt) => void;
};

type PromptsTableProps = { prompts: Prompt[]; data: PromptsResponse; skills: Skill[]; actions: PromptRowActions };

/** Your prompts as a table: click a row to edit it, right-click for everything else. */
export function PromptsTable({ prompts, data, skills, actions }: PromptsTableProps) {
  const t = useTranslations("studioPrompts");
  const ts = useTranslations("studio");
  const tc = useTranslations("common");
  const format = useFormatter();
  const skillNames = new Map(skills.map((s) => [s.id, s.name]));
  // The day of the last edit on the viewer's own calendar, as it always was. Never server-rendered: rows come
  // from promptsResource, whose server snapshot is "loading", so this only runs in the browser after mount.
  // react-doctor-disable-next-line react-doctor/no-locale-format-in-render
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  return (
    <div className="overflow-hidden rounded-xl border bg-card shadow-xs">
      <Table>
        <TableHeader className="bg-muted/50">
          <TableRow>
            <TableHead className="w-14 ps-4">{t("table.number")}</TableHead>
            <TableHead>{tc("fields.name")}</TableHead>
            <TableHead>{t("role")}</TableHead>
            <TableHead className="hidden lg:table-cell">{t("skills")}</TableHead>
            <TableHead className="hidden text-end sm:table-cell">{t("table.updated")}</TableHead>
            <TableHead className="w-12">
              <span className="sr-only">{tc("actions.delete")}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {prompts.map((prompt, index) => {
            const inUse = data.active[prompt.role] === prompt.id;
            const attached = prompt.skill_ids.flatMap((id) => skillNames.get(id) ?? []);
            const roleName = ts(`roles.${prompt.role}.name`);
            return (
              <ContextMenu key={prompt.id}>
                <ContextMenuTrigger asChild>
                  <TableRow className="cursor-pointer" onClick={() => actions.edit(prompt)}>
                    <TableCell className="ps-4 font-mono text-muted-foreground tabular-nums">
                      {format.number(index + 1, { minimumIntegerDigits: 2 })}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-0.5">
                        <span className="flex items-center gap-2 font-medium">
                          <span dir="auto">{prompt.name}</span>
                          {inUse ? (
                            <Badge className="gap-1 rounded-md">
                              <Check />
                              {t("table.inUse")}
                            </Badge>
                          ) : null}
                        </span>
                        <span className="font-mono text-muted-foreground text-xs">{prompt.id.slice(0, 8)}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="rounded-md">
                        {roleName}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden max-w-64 truncate text-muted-foreground lg:table-cell">
                      {attached.length ? format.list(attached, { type: "unit", style: "short" }) : "—"}
                    </TableCell>
                    <TableCell className="hidden text-end text-muted-foreground tabular-nums sm:table-cell">
                      {format.dateTime(new Date(prompt.updated_at), "medium", { timeZone })}
                    </TableCell>
                    <TableCell onClick={(event) => event.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={t("table.deleteNamed", { name: prompt.name })}
                        onClick={() => actions.remove(prompt)}
                      >
                        <Trash2 />
                      </Button>
                    </TableCell>
                  </TableRow>
                </ContextMenuTrigger>
                <ContextMenuContent className="w-56">
                  <K.Item onSelect={() => actions.edit(prompt)}>
                    <Pencil />
                    {t("menu.edit")}
                  </K.Item>
                  <K.Item onSelect={() => void setPromptInUse(prompt, !inUse, t, ts)}>
                    {inUse ? <ZapOff /> : <Zap />}
                    {inUse ? t("menu.stopUsing") : t("menu.useFor", { role: roleName })}
                  </K.Item>
                  <K.Item onSelect={() => actions.duplicate(prompt)}>
                    <Copy />
                    {t("menu.duplicate")}
                  </K.Item>
                  <K.Separator />
                  <K.Item variant="destructive" onSelect={() => actions.remove(prompt)}>
                    <Trash2 />
                    {t("menu.delete")}
                  </K.Item>
                </ContextMenuContent>
              </ContextMenu>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
