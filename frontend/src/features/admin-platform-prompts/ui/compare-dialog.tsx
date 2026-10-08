"use client";

import { type ReactNode, useId, useState } from "react";

import { cn } from "cn";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { FieldLabel } from "@/components/ui/field-text";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Switch } from "@/components/ui/switch";

import { configToText, type DiffRow, diffLines } from "../domain/config-diff";
import { formatDateTime } from "../domain/format";
import { usePlatformPrompts } from "../model/platform-prompts-provider";

/** "draft" or a version id. */
type Side = string;

function DiffCell({ text, tone }: { text: string | null; tone: "same" | "removed" | "added" }) {
  return (
    <div
      className={cn(
        "min-h-5 whitespace-pre-wrap break-words px-2 font-mono text-xs leading-5",
        tone === "removed" && text !== null && "bg-destructive/10 text-destructive",
        tone === "added" && text !== null && "bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
        text === null && "bg-muted/40",
      )}
    >
      {text === null ? null : (
        <>
          {tone === "same" ? null : <span className="sr-only">{tone === "removed" ? "Удалено: " : "Добавлено: "}</span>}
          {text === "" ? " " : text}
        </>
      )}
    </div>
  );
}

function DiffTable({ rows, changesOnly }: { rows: DiffRow[]; changesOnly: boolean }) {
  const visible = rows
    .map((row, index) => ({ row, line: index + 1 }))
    .filter(({ row }) => !changesOnly || row.kind === "changed");

  if (visible.length === 0) {
    return <p className="p-6 text-center text-muted-foreground text-sm">Различий нет — конфигурации совпадают.</p>;
  }

  return (
    <div className="grid grid-cols-2 divide-x">
      {visible.map(({ row, line }) => (
        <div key={line} className="contents">
          <DiffCell text={row.left} tone={row.kind === "same" ? "same" : "removed"} />
          <DiffCell text={row.right} tone={row.kind === "same" ? "same" : "added"} />
        </div>
      ))}
    </div>
  );
}

function CompareBody({ initialLeft, initialRight }: { initialLeft: Side; initialRight: Side }) {
  const {
    state: { config, versions },
  } = usePlatformPrompts();
  const [left, setLeft] = useState(initialLeft);
  const [right, setRight] = useState(initialRight);
  const [changesOnly, setChangesOnly] = useState(false);
  const ids = useId();

  const configOf = (side: Side) =>
    side === "draft" ? config : (versions.find((version) => version.id === side)?.config ?? config);
  const rows = diffLines(configToText(configOf(left)), configToText(configOf(right)));
  const changed = rows.filter((row) => row.kind === "changed").length;

  const options = [
    { id: "draft", label: "Черновик (текущий)" },
    ...versions.map((version) => ({
      id: version.id,
      label: `Версия ${version.number} · ${formatDateTime(version.published_at)}`,
    })),
  ];
  const picker = (id: string, label: string, value: Side, onChange: (value: Side) => void) => (
    <Field className="min-w-0">
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <NativeSelect id={id} value={value} onChange={(event) => onChange(event.currentTarget.value)} className="w-full">
        {options.map((option) => (
          <NativeSelectOption key={option.id} value={option.id}>
            {option.label}
          </NativeSelectOption>
        ))}
      </NativeSelect>
    </Field>
  );

  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        {picker(`${ids}-left`, "Было", left, setLeft)}
        {picker(`${ids}-right`, "Стало", right, setRight)}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="text-muted-foreground" aria-live="polite">
          {changed === 0 ? "Без изменений" : `Изменённых строк: ${changed}`}
        </span>
        <Field orientation="horizontal" className="w-auto">
          <Switch id={`${ids}-changes`} checked={changesOnly} onCheckedChange={setChangesOnly} size="sm" />
          <FieldLabel htmlFor={`${ids}-changes`} className="font-normal text-xs">
            Только изменения
          </FieldLabel>
        </Field>
      </div>
      <div className="max-h-[60vh] overflow-auto rounded-lg border">
        <DiffTable rows={rows} changesOnly={changesOnly} />
      </div>
    </>
  );
}

/** Side-by-side text comparison of any two of: the draft and the published versions. */
export function CompareDialog({
  initialLeft,
  initialRight,
  children,
}: {
  initialLeft: Side;
  initialRight: Side;
  /** The button that opens the dialog. */
  children: ReactNode;
}) {
  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent showCloseButton={false} className="sm:max-w-5xl">
        <DialogHeader>
          <DialogTitle>Сравнение версий</DialogTitle>
          <DialogDescription>Слева — удалённые строки, справа — добавленные.</DialogDescription>
        </DialogHeader>
        <CompareBody initialLeft={initialLeft} initialRight={initialRight} />
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Закрыть</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
