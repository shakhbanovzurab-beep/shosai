"use client";

import { type FormEvent, useState, useTransition } from "react";

import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldGroup } from "@/components/ui/field";
import { FieldDescription, FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Spinner } from "@/components/ui/spinner";

import type { Tier } from "../domain/contract";
import { addModel } from "../model/catalogue-actions";

const BY_PRICE = "price";
const TIERS: { value: Tier | typeof BY_PRICE; label: string }[] = [
  { value: BY_PRICE, label: "По цене" },
  { value: "standard", label: "Стандартный" },
  { value: "frontier", label: "Frontier" },
];

/** Добавление модели по её id в OpenRouter; описание и возможности сервер берёт из списка OpenRouter. */
export function AddModelDialog() {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Plus aria-hidden="true" />
          Добавить модель
        </Button>
      </DialogTrigger>
      <DialogContent>{open ? <AddModelForm onDone={() => setOpen(false)} /> : null}</DialogContent>
    </Dialog>
  );
}

/** Смонтирована на одно открытие: id и ошибка каждый раз начинаются заново. */
function AddModelForm({ onDone }: { onDone: () => void }) {
  const [openrouterId, setOpenrouterId] = useState("");
  const [tier, setTier] = useState<string>(BY_PRICE);
  const [problem, setProblem] = useState<string | null>(null);
  const [saving, startSaving] = useTransition();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const chosen = tier === "standard" || tier === "frontier" ? tier : null;
    startSaving(async () => {
      const failure = await addModel(openrouterId, chosen);
      if (failure === null) onDone();
      else setProblem(failure);
    });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>Добавить модель</DialogTitle>
        <DialogDescription>
          Название, контекст и возможности придут из списка OpenRouter. Модель появится выключенной.
        </DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field data-invalid={problem ? "" : undefined}>
          <FieldLabel htmlFor="ai-model-id">Id в OpenRouter</FieldLabel>
          <Input
            id="ai-model-id"
            value={openrouterId}
            onChange={(event) => setOpenrouterId(event.currentTarget.value)}
            placeholder="anthropic/claude-sonnet-5"
            autoComplete="off"
            spellCheck={false}
            maxLength={128}
            aria-invalid={problem ? true : undefined}
            required
          />
          {problem ? <FieldError>{problem}</FieldError> : null}
        </Field>
        <Field>
          <FieldLabel htmlFor="ai-model-tier">Уровень</FieldLabel>
          <NativeSelect id="ai-model-tier" value={tier} onChange={(event) => setTier(event.currentTarget.value)}>
            {TIERS.map((option) => (
              <NativeSelectOption key={option.value} value={option.value}>
                {option.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          <FieldDescription>
            «По цене» — frontier, если выход дороже линии уровня ($6 за 1 млн токенов по умолчанию).
          </FieldDescription>
        </Field>
      </FieldGroup>
      <DialogFooter>
        <Button type="submit" disabled={saving || openrouterId.trim() === ""}>
          {saving ? <Spinner /> : null}
          Добавить
        </Button>
      </DialogFooter>
    </form>
  );
}
