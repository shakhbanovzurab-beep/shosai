"use client";

import { useState } from "react";

import { cn } from "cn";
import { toast } from "sonner";
import { useFormatter, useTranslations } from "use-intl";

import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

import { MAX_MAX_TOKENS, MIN_MAX_TOKENS, type ModelInfo, type RoleModelSettings } from "../domain/contract";
import type { RoleDefinition } from "../domain/roles";
import { saveRoleSettings } from "../model/save-actions";
import { useProblemWords } from "../model/use-problem-words";
import { ModelPicker } from "./model-picker";

function Unsupported() {
  const t = useTranslations("studio");
  return <span className="text-muted-foreground text-sm">{t("models.unsupported")}</span>;
}

type LabelledProps = { label: string; htmlFor?: string; className?: string; children: React.ReactNode };

function Labelled({ label, htmlFor, className, children }: LabelledProps) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-2", className)}>
      <label htmlFor={htmlFor} className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
        {label}
      </label>
      <div className="flex min-h-9 items-center">{children}</div>
    </div>
  );
}

type RoleModelRowProps = { role: RoleDefinition; settings: RoleModelSettings; models: ModelInfo[] };

// Пункт «По умолчанию» в списке моделей: модель роли выбирает Shosai, на сервер уходит null.
const DEFAULT_CHOICE = "default";

/** One role: which model fills it, and the temperature, output limit and reasoning it runs with. */
export function RoleModelRow({ role, settings, models }: RoleModelRowProps) {
  const t = useTranslations("studio");
  const format = useFormatter();
  const words = useProblemWords();
  const options = models.filter((m) => m.capabilities.includes(role.requires));
  const model = options.find((m) => m.id === settings.model_id);
  const unavailable = settings.model_id !== null && model === undefined;
  // Переключатель действует, когда отвечающая модель рассуждает; модель по умолчанию выбирает Shosai.
  const reasoningApplies = model === undefined || model.supports_reasoning;
  // Only edits in progress live here; otherwise the saved settings are shown.
  const [draggedTemperature, setDraggedTemperature] = useState<number | null>(null);
  const [tokensDraft, setTokensDraft] = useState<string | null>(null);
  const temperature = draggedTemperature ?? settings.temperature;
  const maxTokens = tokensDraft ?? String(settings.max_tokens);
  const id = `role-${role.id}`;
  const roleName = t(`roles.${role.id}.name`);
  const save = (next: RoleModelSettings) => void saveRoleSettings(next, settings, words);
  const defaultChoice = [{ id: DEFAULT_CHOICE, label: t("models.default"), hint: t("models.defaultHint") }];

  const commitMaxTokens = () => {
    const value = Number(maxTokens);
    const limit = Math.min(model?.max_output_tokens ?? MAX_MAX_TOKENS, MAX_MAX_TOKENS);
    if (!Number.isInteger(value) || value < MIN_MAX_TOKENS || value > limit) {
      toast.error(t("models.maxTokensRange", { min: MIN_MAX_TOKENS, max: limit }));
    } else if (value !== settings.max_tokens) save({ ...settings, max_tokens: value });
    setTokensDraft(null);
  };

  return (
    <div className="grid gap-4 px-5 py-5 lg:grid-cols-[minmax(12rem,16rem)_minmax(14rem,1fr)_12rem_8rem_8rem] lg:items-start">
      <div className="flex flex-col gap-1">
        <h3 className="font-medium">{roleName}</h3>
        <p className="text-muted-foreground text-sm">{t(`roles.${role.id}.description`)}</p>
      </div>
      <Labelled label={t("models.model")} htmlFor={`${id}-model`}>
        <div className="flex w-full flex-col gap-1.5">
          <ModelPicker
            id={`${id}-model`}
            models={options}
            options={defaultChoice}
            value={unavailable ? DEFAULT_CHOICE : (settings.model_id ?? DEFAULT_CHOICE)}
            onChange={(choice) => save({ ...settings, model_id: choice === DEFAULT_CHOICE ? null : choice })}
            label={t("models.modelFor", { role: roleName })}
          />
          {unavailable ? <p className="text-muted-foreground text-xs">{t("models.unavailable")}</p> : null}
        </div>
      </Labelled>
      <Labelled label={t("models.temperature")}>
        {model?.supports_temperature === false ? (
          <Unsupported />
        ) : (
          <div className="flex w-full items-center gap-3">
            <Slider
              min={0}
              max={2}
              step={0.1}
              value={[temperature]}
              onValueChange={([value]) => setDraggedTemperature(value)}
              onValueCommit={([value]) => {
                setDraggedTemperature(null);
                save({ ...settings, temperature: value });
              }}
              aria-label={t("models.temperatureFor", { role: roleName })}
            />
            <span className="w-7 text-end font-mono text-sm tabular-nums">
              {format.number(temperature, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
            </span>
          </div>
        )}
      </Labelled>
      <Labelled label={t("models.maxTokens")} htmlFor={`${id}-tokens`}>
        <Input
          id={`${id}-tokens`}
          inputMode="numeric"
          value={maxTokens}
          onChange={(event) => setTokensDraft(event.currentTarget.value.replace(/\D/g, ""))}
          onBlur={commitMaxTokens}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
          }}
          className="font-mono tabular-nums"
        />
      </Labelled>
      {/* В строке таблицы переключатель стоит по центру своей колонки, под подписью. */}
      <Labelled
        label={t("models.reasoning")}
        htmlFor={reasoningApplies ? `${id}-reasoning` : undefined}
        className="lg:items-center lg:text-center"
      >
        {reasoningApplies ? (
          <Switch
            id={`${id}-reasoning`}
            checked={settings.reasoning}
            onCheckedChange={(reasoning) => save({ ...settings, reasoning })}
          />
        ) : (
          <Unsupported />
        )}
      </Labelled>
    </div>
  );
}
