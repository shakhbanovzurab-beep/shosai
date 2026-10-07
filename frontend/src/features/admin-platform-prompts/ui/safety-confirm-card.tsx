"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field";

import { CONFIRM_ACTIONS } from "../domain/contract";
import { useSafety } from "../model/use-safety";

export function ConfirmActionsCard() {
  const { safety, set } = useSafety();
  const selected = new Set(safety.confirm_actions);

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <CardTitle>Всегда с подтверждением</CardTitle>
        <CardDescription>
          Перед этими действиями Leo показывает, что собирается сделать, и ждёт согласия пользователя.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <FieldSet>
          <FieldLegend className="sr-only">Действия, требующие подтверждения</FieldLegend>
          <div className="flex flex-col gap-3">
            {CONFIRM_ACTIONS.map((action) => (
              <Field key={action.id} orientation="horizontal">
                <Checkbox
                  id={`confirm-${action.id}`}
                  checked={selected.has(action.id)}
                  onCheckedChange={(checked) =>
                    set(() => ({
                      confirm_actions: CONFIRM_ACTIONS.map((a) => a.id).filter((id) =>
                        id === action.id ? checked === true : selected.has(id),
                      ),
                    }))
                  }
                />
                <FieldLabel htmlFor={`confirm-${action.id}`} className="font-normal">
                  {action.label}
                </FieldLabel>
              </Field>
            ))}
          </div>
        </FieldSet>
      </CardContent>
    </Card>
  );
}
