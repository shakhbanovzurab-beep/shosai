"use client";

import { type ReactNode, useId, useState } from "react";

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
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";

import { configToText, diffLines } from "../domain/config-diff";
import type { PlatformConfig } from "../domain/contract";
import { formatDateTime } from "../domain/format";
import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { useVersion, useVersions } from "../model/versions";
import { DiffTable } from "./diff-table";

/** "draft" или id версии. */
type Side = string;

/** Конфигурация стороны сравнения: черновик и действующая версия уже здесь, остальные читаются по id. */
function useSide(side: Side): { config: PlatformConfig | null; failed: boolean } {
  const {
    state: { config, published },
  } = usePlatformPrompts();
  let local: PlatformConfig | null = null;
  if (side === "draft") local = config;
  else if (side === published?.id) local = published.config;
  const version = useVersion(local === null ? side : null);
  return { config: local ?? version.data?.config ?? null, failed: version.isError };
}

function SideDiff({ left, right, changesOnly }: { left: Side; right: Side; changesOnly: boolean }) {
  const before = useSide(left);
  const after = useSide(right);
  if (before.failed || after.failed) {
    return <p className="p-6 text-center text-destructive text-sm">Не удалось загрузить версию. Обновите страницу.</p>;
  }
  if (before.config === null || after.config === null) {
    return (
      <div className="flex justify-center p-6" role="status" aria-label="Загрузка версии">
        <Spinner />
      </div>
    );
  }
  const rows = diffLines(configToText(before.config), configToText(after.config));
  return <DiffTable rows={rows} changesOnly={changesOnly} />;
}

function CompareBody({ initialLeft, initialRight }: { initialLeft: Side; initialRight: Side }) {
  const {
    state: { published },
  } = usePlatformPrompts();
  const { versions } = useVersions();
  const [left, setLeft] = useState(initialLeft);
  const [right, setRight] = useState(initialRight);
  const [changesOnly, setChangesOnly] = useState(false);
  const ids = useId();

  const listed = published && !versions.some((version) => version.id === published.id) ? [published] : [];
  const options = [
    { id: "draft", label: "Черновик (текущий)" },
    ...[...listed, ...versions].map((version) => ({
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
      <Field orientation="horizontal" className="w-auto self-end">
        <Switch id={`${ids}-changes`} checked={changesOnly} onCheckedChange={setChangesOnly} size="sm" />
        <FieldLabel htmlFor={`${ids}-changes`} className="font-normal text-xs">
          Только изменения
        </FieldLabel>
      </Field>
      <div className="max-h-[60vh] overflow-auto rounded-lg border">
        <SideDiff left={left} right={right} changesOnly={changesOnly} />
      </div>
    </>
  );
}

/** Сравнение бок о бок любых двух: черновика и опубликованных версий. */
export function CompareDialog({
  initialLeft,
  initialRight,
  children,
}: {
  initialLeft: Side;
  initialRight: Side;
  /** Кнопка, которая открывает окно. */
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
