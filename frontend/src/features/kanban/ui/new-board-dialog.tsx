"use client";

import { useActionState, useState } from "react";

import { useRouter } from "next/navigation";

import { cn } from "cn";
import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

import {
  BOARD_ICONS,
  BOARD_NAME_MAX,
  BOARD_TEMPLATE_IDS,
  BOARD_TEMPLATES,
  type BoardIcon,
  type BoardTemplate,
  boardHref,
} from "../domain/board";
import { createBoard } from "../model/board-actions";
import { BOARD_ICON_GLYPHS, BOARD_ICON_NAMES } from "./board-icons";

const optionClass = (selected: boolean) =>
  cn(
    "cursor-pointer rounded-lg border outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50",
    selected ? "border-primary bg-primary/5" : "hover:bg-muted",
  );

/** A template's starting columns in their order, the arrows pointing the way the line reads. */
function TemplateColumns({ template }: { template: BoardTemplate }) {
  const t = useTranslations("kanbanBoards");
  return (
    <span className="flex flex-wrap items-center gap-x-1 text-muted-foreground text-xs">
      {BOARD_TEMPLATES[template].map((column, index) => (
        <span key={column.name} className="flex items-center gap-x-1">
          {index > 0 ? <ArrowRight className="size-3 rtl:-scale-x-100" aria-hidden="true" /> : null}
          {t(`columnNames.${column.name}`)}
        </span>
      ))}
    </span>
  );
}

/** The form is mounted per opening, so every new board starts from the defaults. */
function NewBoardForm({ onDone }: { onDone: () => void }) {
  const t = useTranslations("kanbanBoards");
  const tc = useTranslations("common");
  const router = useRouter();
  const [icon, setIcon] = useState<BoardIcon>("briefcase");
  const [template, setTemplate] = useState<BoardTemplate>("simple");
  const [, submit, pending] = useActionState(async (_: null, form: FormData) => {
    const name = String(form.get("name") ?? "").trim();
    const board = await createBoard({ name, icon, template }, t);
    if (board) {
      onDone();
      router.push(boardHref(board.id));
    }
    return null;
  }, null);

  return (
    <form action={submit} className="flex flex-col gap-5">
      <DialogHeader>
        <DialogTitle>{t("newBoard.title")}</DialogTitle>
        <DialogDescription>{t("newBoard.description")}</DialogDescription>
      </DialogHeader>
      <div className="flex flex-col gap-2">
        <Label htmlFor="board-name">{tc("fields.name")}</Label>
        <Input
          id="board-name"
          name="name"
          required
          maxLength={BOARD_NAME_MAX}
          placeholder={t("newBoard.namePlaceholder")}
          autoComplete="off"
        />
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 font-medium text-sm">{t("newBoard.icon")}</legend>
        <div className="grid grid-cols-5 gap-2">
          {BOARD_ICONS.map((value) => {
            const Icon = BOARD_ICON_GLYPHS[value];
            const label = t(`icons.${BOARD_ICON_NAMES[value]}`);
            return (
              <button
                key={value}
                type="button"
                aria-pressed={icon === value}
                aria-label={label}
                title={label}
                onClick={() => setIcon(value)}
                className={cn("flex h-10 items-center justify-center", optionClass(icon === value))}
              >
                <Icon className="size-4" aria-hidden="true" />
              </button>
            );
          })}
        </div>
      </fieldset>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 font-medium text-sm">{t("newBoard.columns")}</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {BOARD_TEMPLATE_IDS.map((id) => (
            <button
              key={id}
              type="button"
              aria-pressed={template === id}
              onClick={() => setTemplate(id)}
              className={cn("flex flex-col gap-1 p-3 text-start", optionClass(template === id))}
            >
              <span className="font-medium text-sm">{t(`templates.${id}`)}</span>
              <TemplateColumns template={id} />
            </button>
          ))}
        </div>
      </fieldset>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          {tc("actions.cancel")}
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("newBoard.create")}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function NewBoardDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {open ? <NewBoardForm onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
