"use client";

import { useEffect, useEffectEvent, useState } from "react";

import { cn } from "cn";
import { RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

import { type ComboProblem, comboFromEvent, comboKeys, comboProblem, type HotkeyId } from "../../domain/hotkeys";
import { useIsMac } from "../../model/use-is-mac";

type HotkeyRowProps = {
  id: HotkeyId;
  combo: string | null;
  bindings: Record<HotkeyId, string | null>;
  customized: boolean;
  onChange: (combo: string | null) => void;
  onReset: () => void;
};

/** A combo's keys in the order they're pressed, left to right in either interface direction, like a keyboard. */
const KeyCombo = ({ keys }: { keys: string }) => (
  <span dir="ltr" className="tracking-[0.2em]">
    {keys}
  </span>
);

/**
 * One shortcut: its name, and a key box that records a new combo when clicked. While recording it
 * listens before everything else on the page, so the keys don't also trigger the page's own shortcuts
 * or close the dialog. Esc cancels, Backspace turns the shortcut off.
 */
export function HotkeyRow({ id, combo, bindings, customized, onChange, onReset }: HotkeyRowProps) {
  const t = useTranslations("settingsHotkeys");
  const isMac = useIsMac();
  const [recording, setRecording] = useState(false);
  const [problem, setProblem] = useState<ComboProblem | null>(null);
  const command = t(`commands.${id}`);

  const stop = () => {
    setRecording(false);
    setProblem(null);
  };

  const onKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (event.key === "Tab") return stop();
    event.preventDefault();
    event.stopPropagation();
    if (event.key === "Escape") return stop();
    if (event.key === "Backspace" || event.key === "Delete") {
      stop();
      return onChange(null);
    }
    const next = comboFromEvent(event, isMac);
    if (!next) return;
    const issue = comboProblem(next, id, bindings);
    if (issue) return setProblem(issue);
    stop();
    onChange(next);
  });

  useEffect(() => {
    if (!recording) return;
    const listener = (event: KeyboardEvent) => onKeyDown(event);
    window.addEventListener("keydown", listener, { capture: true });
    return () => window.removeEventListener("keydown", listener, { capture: true });
  }, [recording]);

  const hintId = `hotkey-${id}-hint`;
  const keys = combo ? comboKeys(combo, isMac).join(" ") : null;
  let shown = <span className="text-muted-foreground">{t("off")}</span>;
  if (recording) shown = <span className="text-primary">{t("pressKeys")}</span>;
  else if (keys) shown = <KeyCombo keys={keys} />;
  let label = keys ? t("change", { command, keys }) : t("changeOff", { command });
  if (recording) label = t("record", { command });
  let hint = t("hint");
  if (problem?.code === "taken") hint = t("problems.taken", { command: t(`commands.${problem.owner}`) });
  else if (problem) hint = t(`problems.${problem.code}`);

  return (
    <div className="flex flex-col gap-1.5 px-4 py-3">
      <div className="flex items-center justify-between gap-4">
        <span className="font-medium text-sm">{command}</span>
        <div className="flex shrink-0 items-center gap-1">
          {customized && !recording ? (
            <Button variant="ghost" size="icon-sm" onClick={onReset} aria-label={t("reset", { command })}>
              <RotateCcw />
            </Button>
          ) : null}
          <button
            type="button"
            onClick={() => (recording ? stop() : setRecording(true))}
            onBlur={stop}
            aria-label={label}
            aria-describedby={recording ? hintId : undefined}
            className={cn(
              "flex h-9 min-w-32 cursor-pointer items-center justify-center rounded-lg border bg-background px-4 font-medium font-mono text-sm outline-none transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
              recording && "border-primary bg-primary/5 hover:bg-primary/5",
            )}
          >
            {shown}
          </button>
        </div>
      </div>
      {recording ? (
        <p
          id={hintId}
          role="status"
          className={cn("text-end text-xs", problem ? "text-destructive" : "text-muted-foreground")}
        >
          {hint}
        </p>
      ) : null}
    </div>
  );
}
