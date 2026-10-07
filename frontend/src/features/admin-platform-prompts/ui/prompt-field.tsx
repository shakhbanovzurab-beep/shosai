"use client";

import { useRef } from "react";

import { cn } from "cn";
import { Braces } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";

import { PLACEHOLDERS } from "../domain/contract";
import { approxTokens, formatNumber, unknownPlaceholders } from "../domain/format";

type PromptFieldProps = {
  id: string;
  /** Accessible name of the textarea when no visible <label> points at it. */
  label: string;
  value: string;
  onChange: (value: string) => void;
  maxChars: number;
  placeholder?: string;
  className?: string;
};

/** A prompt editor: monospace text, a placeholder picker that inserts at the caret, and a size estimate. */
export function PromptField({ id, label, value, onChange, maxChars, placeholder, className }: PromptFieldProps) {
  const textarea = useRef<HTMLTextAreaElement>(null);
  const tooLong = value.length > maxChars;
  const unknown = unknownPlaceholders(value);

  const insert = (token: string) => {
    const element = textarea.current;
    const start = element?.selectionStart ?? value.length;
    const end = element?.selectionEnd ?? value.length;
    onChange(value.slice(0, start) + token + value.slice(end));
    requestAnimationFrame(() => {
      element?.focus();
      element?.setSelectionRange(start + token.length, start + token.length);
    });
  };

  return (
    <div className="flex flex-col gap-2">
      <Textarea
        ref={textarea}
        id={id}
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.currentTarget.value)}
        placeholder={placeholder}
        spellCheck={false}
        aria-invalid={tooLong}
        aria-describedby={`${id}-meta`}
        className={cn("min-h-40 font-mono text-sm leading-6", className)}
      />
      <div id={`${id}-meta`} className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className={cn("tabular-nums", tooLong ? "text-destructive" : "text-muted-foreground")}>
          {formatNumber(value.length)} / {formatNumber(maxChars)} символов · ≈{formatNumber(approxTokens(value))}{" "}
          токенов
          {tooLong ? " — сократите, чтобы сохранить" : null}
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" variant="ghost" size="xs">
              <Braces data-icon="inline-start" />
              Вставить переменную
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-72">
            <DropdownMenuLabel>Подставляется в каждом запросе</DropdownMenuLabel>
            {PLACEHOLDERS.map((placeholder) => (
              <DropdownMenuItem
                key={placeholder.key}
                onSelect={() => insert(`{{${placeholder.key}}}`)}
                className="flex-col items-start gap-0.5"
              >
                <code className="font-mono text-xs">{`{{${placeholder.key}}}`}</code>
                <span className="text-muted-foreground text-xs">{placeholder.description}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {unknown.length > 0 ? (
        <p className="text-amber-700 text-xs dark:text-amber-400" role="status">
          Неизвестные переменные останутся как есть: {unknown.map((key) => `{{${key}}}`).join(", ")}
        </p>
      ) : null}
    </div>
  );
}
