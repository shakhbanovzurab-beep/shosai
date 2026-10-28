"use client";

import { cn } from "cn";

import { Textarea } from "@/components/ui/textarea";

import { formatNumber } from "../domain/format";
import { estimateTokens } from "../domain/platform-layer";
import { NotEnglishHint } from "./not-english-hint";

type PromptFieldProps = {
  id: string;
  /** Доступное имя поля, когда на него не указывает видимый <label>. */
  label: string;
  value: string;
  onChange: (value: string) => void;
  maxChars: number;
  /** Сколько токенов может занять текст; без бюджета показывается только оценка. */
  tokenBudget?: number;
  placeholder?: string;
  className?: string;
};

/** Редактор промта: моноширинный текст, его размер в символах и токенах и подсказка, если текст не английский. */
export function PromptField({
  id,
  label,
  value,
  onChange,
  maxChars,
  tokenBudget,
  placeholder,
  className,
}: PromptFieldProps) {
  const tooLong = value.length > maxChars;
  const tokens = estimateTokens(value.trim());
  const overBudget = tokenBudget !== undefined && tokens > tokenBudget;

  return (
    <div className="flex flex-col gap-2">
      <Textarea
        id={id}
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.currentTarget.value)}
        placeholder={placeholder}
        spellCheck={false}
        lang="en"
        aria-invalid={tooLong || overBudget}
        aria-describedby={`${id}-meta`}
        className={cn("min-h-40 font-mono text-sm leading-6", className)}
      />
      <p
        id={`${id}-meta`}
        className={cn("text-xs tabular-nums", tooLong || overBudget ? "text-destructive" : "text-muted-foreground")}
      >
        {formatNumber(value.length)} / {formatNumber(maxChars)} символов · ≈{formatNumber(tokens)}
        {tokenBudget === undefined ? null : ` из ${formatNumber(tokenBudget)}`} токенов
        {tooLong ? " — сократите, чтобы сохранить" : null}
        {overBudget ? " — сократите, чтобы опубликовать" : null}
      </p>
      <NotEnglishHint text={value} />
    </div>
  );
}
