"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldContent, FieldLegend, FieldSet } from "@/components/ui/field";
import { FieldDescription, FieldLabel, FieldTitle } from "@/components/ui/field-text";

import { OVERRIDABLE_SETTINGS } from "../domain/contract";
import { useBehavior } from "../model/use-behavior";

export function OverridesCard() {
  const { behavior, set } = useBehavior();
  const allowed = new Set(behavior.user_overrides);

  return (
    <Card className="shadow-xs lg:col-span-2">
      <CardHeader>
        <CardTitle>Что пользователи могут менять</CardTitle>
        <CardDescription>
          Отмеченное доступно в Studio и настройках Leo. Остальное фиксируется значениями выше.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <FieldSet>
          <FieldLegend className="sr-only">Разрешённые пользовательские настройки</FieldLegend>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {OVERRIDABLE_SETTINGS.map((setting) => (
              <FieldLabel key={setting.id} htmlFor={`override-${setting.id}`}>
                <Field orientation="horizontal">
                  <Checkbox
                    id={`override-${setting.id}`}
                    checked={allowed.has(setting.id)}
                    onCheckedChange={(checked) =>
                      set({
                        user_overrides: OVERRIDABLE_SETTINGS.map((s) => s.id).filter((id) =>
                          id === setting.id ? checked === true : allowed.has(id),
                        ),
                      })
                    }
                  />
                  <FieldContent>
                    <FieldTitle>{setting.label}</FieldTitle>
                    <FieldDescription>{setting.description}</FieldDescription>
                  </FieldContent>
                </Field>
              </FieldLabel>
            ))}
          </div>
        </FieldSet>
      </CardContent>
    </Card>
  );
}
