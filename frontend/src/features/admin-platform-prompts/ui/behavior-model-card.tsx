"use client";

import { useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { useStudioModels } from "@/features/studio";

import { OUTPUT_TOKENS_MAX, OUTPUT_TOKENS_MIN, TEMPERATURE_MAX, TEMPERATURE_MIN } from "../domain/contract";
import { formatNumber } from "../domain/format";
import { useBehavior } from "../model/use-behavior";

const temperatureFormat = new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
/** Model ids the subscription offers, as suggestions; any id can still be typed in. */
function ModelField() {
  const { behavior, set } = useBehavior();
  const models = useStudioModels();
  const options = models.status === "ready" ? models.data.models.filter((m) => m.capabilities.includes("text")) : [];
  const empty = behavior.default_model.trim().length === 0;

  return (
    <Field data-invalid={empty}>
      <FieldLabel htmlFor="behavior-model">Модель по умолчанию</FieldLabel>
      <Input
        id="behavior-model"
        list="behavior-model-options"
        value={behavior.default_model}
        onChange={(event) => set({ default_model: event.currentTarget.value })}
        placeholder="auto"
        autoComplete="off"
        spellCheck={false}
        aria-invalid={empty}
        className="font-mono"
      />
      <datalist id="behavior-model-options">
        <option value="auto">Leo выбирает модель под задачу</option>
        {options.map((model) => (
          <option key={model.id} value={model.id}>
            {model.name} · {model.provider}
          </option>
        ))}
      </datalist>
      {empty ? (
        <FieldError>Укажите id модели или «auto».</FieldError>
      ) : (
        <FieldDescription>
          «auto» — Leo выбирает сам. Если модели нет в подписке пользователя, используется её модель по умолчанию.
        </FieldDescription>
      )}
    </Field>
  );
}

/** Keeps the typed text while it is out of range, and only commits whole numbers inside the limits. */
function MaxTokensField() {
  const { behavior, set } = useBehavior();
  const [text, setText] = useState(String(behavior.max_output_tokens));
  const parsed = Number(text);
  const valid = Number.isInteger(parsed) && parsed >= OUTPUT_TOKENS_MIN && parsed <= OUTPUT_TOKENS_MAX;

  return (
    <Field data-invalid={!valid}>
      <FieldLabel htmlFor="behavior-max-tokens">Максимум токенов в ответе</FieldLabel>
      <Input
        id="behavior-max-tokens"
        type="number"
        inputMode="numeric"
        min={OUTPUT_TOKENS_MIN}
        max={OUTPUT_TOKENS_MAX}
        step={256}
        value={text}
        onChange={(event) => {
          const value = event.currentTarget.value;
          setText(value);
          const next = Number(value);
          if (Number.isInteger(next) && next >= OUTPUT_TOKENS_MIN && next <= OUTPUT_TOKENS_MAX)
            set({ max_output_tokens: next });
        }}
        aria-invalid={!valid}
        className="tabular-nums"
      />
      {valid ? (
        <FieldDescription>
          Ограничение длины одного ответа. Пользовательские лимиты не могут его превышать.
        </FieldDescription>
      ) : (
        <FieldError>
          Целое число от {formatNumber(OUTPUT_TOKENS_MIN)} до {formatNumber(OUTPUT_TOKENS_MAX)}.
        </FieldError>
      )}
    </Field>
  );
}
export function BehaviorModelCard() {
  const { behavior, set } = useBehavior();

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <CardTitle>Модель</CardTitle>
        <CardDescription>Параметры генерации для всех разговоров.</CardDescription>
      </CardHeader>
      <CardContent>
        <FieldGroup>
          <ModelField />
          <Field>
            <div className="flex items-center justify-between gap-2">
              <FieldLabel htmlFor="behavior-temperature">Температура</FieldLabel>
              <span className="font-mono text-muted-foreground text-sm tabular-nums" aria-hidden="true">
                {temperatureFormat.format(behavior.temperature)}
              </span>
            </div>
            <Slider
              id="behavior-temperature"
              min={TEMPERATURE_MIN}
              max={TEMPERATURE_MAX}
              step={0.1}
              value={[behavior.temperature]}
              onValueChange={([temperature]) => set({ temperature: Math.round(temperature * 10) / 10 })}
              aria-label="Температура"
            />
            <FieldDescription>0 — точно и предсказуемо, 2 — максимально свободно.</FieldDescription>
          </Field>
          <MaxTokensField />
        </FieldGroup>
      </CardContent>
    </Card>
  );
}
