"use client";

import { useId, useState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldContent, FieldGroup } from "@/components/ui/field";
import { FieldLabel } from "@/components/ui/field-text";

import { DEFAULT_STOPWATCH_AUTOMATIONS, type StopwatchAutomations } from "../../domain/time-contract";
import { useBoardCommands } from "../board-store";
import { FieldAction, FieldActions } from "./field-card";

const AUTOMATIONS = ["start_on_arrival", "restart_on_move", "stop_on_done"] as const;

const automationsOf = (on: (key: (typeof AUTOMATIONS)[number]) => boolean): StopwatchAutomations => ({
  start_on_arrival: on("start_on_arrival"),
  restart_on_move: on("restart_on_move"),
  stop_on_done: on("stop_on_done"),
});

/** Три автоматизации секундомера доски флажками (KT-D2); сохраняются вместе. */
function AutomationsForm({ value, onDone }: { value: StopwatchAutomations; onDone: () => void }) {
  const t = useTranslations("kanbanFields");
  const tc = useTranslations("common");
  const { fields } = useBoardCommands();
  const id = useId();
  return (
    <form
      className="flex flex-col gap-5"
      onSubmit={(event) => {
        event.preventDefault();
        // Флажки живут в самой форме; при сохранении читаются все три.
        const form = new FormData(event.currentTarget);
        onDone();
        void fields.setAutomations(automationsOf((key) => form.get(key) === "on"));
      }}
    >
      <DialogHeader>
        <DialogTitle>{t("automations.title")}</DialogTitle>
      </DialogHeader>
      <FieldGroup>
        {AUTOMATIONS.map((key) => (
          <Field key={key} orientation="horizontal">
            <Checkbox id={`${id}-${key}`} name={key} defaultChecked={value[key]} />
            <FieldContent>
              <FieldLabel htmlFor={`${id}-${key}`} className="font-normal">
                {t(`automations.${key}`)}
              </FieldLabel>
            </FieldContent>
          </Field>
        ))}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          {tc("actions.cancel")}
        </Button>
        <Button type="submit">{tc("actions.save")}</Button>
      </DialogFooter>
    </form>
  );
}

/** «Настроить» у секундомера и сколько автоматизаций включено. */
export function StopwatchSetup({ automations }: { automations: StopwatchAutomations | undefined }) {
  const t = useTranslations("kanbanFields");
  const [open, setOpen] = useState(false);
  const value = automations ?? DEFAULT_STOPWATCH_AUTOMATIONS;
  const count = AUTOMATIONS.filter((key) => value[key]).length;
  return (
    <FieldActions>
      <FieldAction onClick={() => setOpen(true)}>{t("automations.open")}</FieldAction>
      <span className="text-muted-foreground text-xs">{t("automations.count", { count })}</span>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          {open ? <AutomationsForm value={value} onDone={() => setOpen(false)} /> : null}
        </DialogContent>
      </Dialog>
    </FieldActions>
  );
}
